#!/usr/bin/env python3
"""Parallel runner for CAPTCHA evaluation framework."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from tqdm import tqdm

from actions import Action, CaptchaTask, TaskResult
from agent import Agent
from executor import ActionExecutor
from utils import (
    ACTION_DELAY_MS,
    HALLIGAN_RESPONSE_TIMEOUT,
    BROWSER_HEADLESS,
    BROWSER_SLOW_MO,
    BROWSER_VIEWPORT,
    MAX_CALLS,
    POST_ACTION_DELAY_MS,
    RUNS_DIR,
    get_logger,
)
from parsers.base import CompositeActionParser
from prompt_processor import PromptProcessor
from utils import summarize_results
from providers.base import CaptchaProvider

logger = get_logger(__name__)


class BenchmarkRunner:
    """Orchestrates the parallel benchmark execution."""

    def __init__(
        self,
        server: CaptchaProvider,
        agent_factory: Callable[[], Agent],
        parser: CompositeActionParser,
        workers: int,
        run_timestamp: str,
        prompt_processor_factory: Optional[Callable[[], PromptProcessor]] = None,
        max_calls: int = MAX_CALLS,
    ) -> None:
        self.server = server
        self.agent_factory = agent_factory
        self.parser = parser
        self.workers = workers
        self.run_timestamp = run_timestamp
        self.max_calls = max_calls
        self.run_dir = f"{RUNS_DIR}/{run_timestamp}"
        self.prompt_processor_factory = prompt_processor_factory or PromptProcessor

    async def run(self, tasks: Sequence[CaptchaTask]) -> Dict:
        os.makedirs(self.run_dir, exist_ok=True)
        img_dir = os.path.join(self.run_dir, "img")
        os.makedirs(img_dir, exist_ok=True)

        results: List[TaskResult] = []
        result_queue: asyncio.Queue[TaskResult] = asyncio.Queue()
        queue: asyncio.Queue[CaptchaTask] = asyncio.Queue()
        for task in tasks:
            queue.put_nowait(task)

        progress = tqdm(total=len(tasks), desc="CAPTCHA tasks", leave=False)
        update_lock = asyncio.Lock()

        async with async_playwright() as p:
            browsers = [
                await p.chromium.launch(
                    headless=BROWSER_HEADLESS,
                    slow_mo=BROWSER_SLOW_MO,
                    channel="chromium",
                )
                for _ in range(self.workers)
            ]

            async def worker_loop(worker_id: int) -> None:
                browser = browsers[worker_id]
                while True:
                    try:
                        task = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    result = await self._run_task(browser, task)
                    await result_queue.put(result)

                    async with update_lock:
                        progress.update(1)

                    queue.task_done()

            await asyncio.gather(*(worker_loop(i) for i in range(self.workers)))

            while not result_queue.empty():
                results.append(await result_queue.get())

            for browser in browsers:
                await browser.close()

        progress.close()

        summary = summarize_results(results)
        summary_path = f"{self.run_dir}/captcha-benchmark-results.json"
        with open(summary_path, "w") as handle:
            json.dump(summary, handle, indent=2)
        logger.info("Results saved to %s", summary_path)
        self._print_summary(summary)
        return summary

    async def _run_task(self, browser, task: CaptchaTask) -> TaskResult:
        executor = ActionExecutor()
        prompt_processor = self.prompt_processor_factory()
        agent = self.agent_factory()
        agent.reset()
        prompt_processor.reset_conversation()

        task_id = self._build_task_id(task)
        file_task_id = self._safe_task_id(task_id)

        context = await browser.new_context(viewport=BROWSER_VIEWPORT)
        page = await context.new_page()

        solved = False
        finished_flag = False
        calls_made = 0
        solve_step: Optional[int] = None
        resolved_type = task.captcha_type
        error: Optional[str] = None
        previous_action_rounds: List[Dict] = []

        try:
            await self.server.open_task(page, task)
            await self.server.prepare_task(page, task)
            task_context = await self.server.resolve_task(page, task)
            resolved_type = task_context.resolved_type or resolved_type

            max_calls = self.server.get_max_calls(task, self.max_calls)

            for call_count in range(1, max_calls + 1):
                calls_made = call_count
                actions, action_dicts, current_finished = await self._collect_actions_with_retry(
                    page=page,
                    task=task,
                    call_count=call_count,
                    previous_action_rounds=previous_action_rounds,
                    agent=agent,
                    prompt_processor=prompt_processor,
                    task_id=task_id,
                )
                finished_flag = finished_flag or current_finished

                executable_actions = [
                    action for action in actions if action.type not in {"finished", "terminate"}
                ]

                if not actions:
                    logger.info("No actions parsed for task %s on call %s", task_id, call_count)
                    break

                response_task: Optional[asyncio.Task] = None
                if executable_actions:
                    if self.server.expects_submit_response:
                        action_delay_ms = ACTION_DELAY_MS * len(executable_actions)
                        action_delay_ms += sum(
                            int((action.duration or 5.0) * 1000)
                            for action in executable_actions
                            if action.type == "wait"
                        )
                        response_task = asyncio.create_task(
                            self._wait_for_submit_response(
                                page,
                                HALLIGAN_RESPONSE_TIMEOUT + action_delay_ms,
                            )
                        )
                    success = await executor.execute_actions(
                        page,
                        executable_actions,
                        task.region,
                    )
                    if not success:
                        if response_task:
                            response_task.cancel()
                            try:
                                await response_task
                            except asyncio.CancelledError:
                                pass
                        error = "Action execution failed"
                        break

                previous_action_rounds.append(
                    {
                        "round": call_count,
                        "actions": action_dicts,
                    }
                )

                await page.wait_for_timeout(POST_ACTION_DELAY_MS)

                submit_response = None
                if response_task:
                    try:
                        submit_response = await response_task
                    except PlaywrightTimeoutError:
                        submit_response = None
                    except asyncio.CancelledError:
                        submit_response = None
                    except Exception:
                        submit_response = None

                solved_status = None
                if response_task:
                    if submit_response is not None:
                        try:
                            data = await submit_response.json()
                            solved_status = bool(data.get("solved", False))
                        except Exception:
                            solved_status = None
                else:
                    solved_status = await self.server.check_solved(page, task)
                if solved_status:
                    solved = True
                    solve_step = call_count
                    break

            final_path = os.path.join(self.run_dir, "img", f"test_{file_task_id}.png")
            await self.server.capture_final(page, task, final_path)

        except Exception as exc:
            error = str(exc)
            logger.error("Error running task %s: %s", task_id, exc)

        finally:
            await page.close()
            await context.close()

        return TaskResult(
            task_id=task_id,
            provider_name=task.provider_name,
            requested_type=task.captcha_type,
            resolved_type=resolved_type,
            sample_id=task.sample_id,
            attempt=task.attempt,
            solved=solved,
            calls_made=calls_made,
            finished_flag=finished_flag,
            solve_step=solve_step,
            error=error,
        )

    async def _wait_for_submit_response(self, page, timeout_ms: int):
        if hasattr(page, "wait_for_response"):
            return await page.wait_for_response(lambda r: "/submit" in r.url, timeout=timeout_ms)
        if hasattr(page, "expect_response"):
            async with page.expect_response(lambda r: "/submit" in r.url, timeout=timeout_ms) as response_info:
                return await response_info.value
        return None

    async def _collect_actions_with_retry(
        self,
        page,
        task: CaptchaTask,
        call_count: int,
        previous_action_rounds: List[Dict],
        agent: Agent,
        prompt_processor: PromptProcessor,
        task_id: str,
    ) -> Tuple[List[Action], List[Dict], bool]:
        actions: List[Action] = []
        action_dicts: List[Dict] = []
        finished_flag = False

        for parse_attempt in range(2):
            image, width, height = await self.server.capture_task(page, task)
            instruction = prompt_processor.process_prompt(call_count, previous_action_rounds)
            response = await asyncio.to_thread(
                agent,
                instruction,
                images=[image],
                image_captions=["Current CAPTCHA state"],
            )

            actions = self.parser.parse_response(response, width, height)
            action_dicts = [self._action_to_dict(action) for action in actions]
            finished_flag = finished_flag or prompt_processor.check_finished(call_count, action_dicts)

            if actions:
                break

            if parse_attempt == 0:
                logger.info(
                    "No actions parsed for task %s on call %s; retrying once",
                    task_id,
                    call_count,
                )
                await page.wait_for_timeout(POST_ACTION_DELAY_MS)

        return actions, action_dicts, finished_flag

    def _build_task_id(self, task: CaptchaTask) -> str:
        safe_captcha_type = task.captcha_type.replace("/", "_").replace("\\", "_")
        parts = [task.provider_name, safe_captcha_type]
        if task.sample_id is not None:
            parts.append(str(task.sample_id))
        if task.attempt:
            parts.append(f"attempt{task.attempt}")
        return "_".join(parts)

    def _safe_task_id(self, task_id: str) -> str:
        return task_id.replace("/", "_").replace("\\", "_")

    def _action_to_dict(self, action: Action) -> Dict:
        payload = asdict(action)
        payload.pop("description", None)
        return payload

    def _print_summary(self, summary: Dict) -> None:
        summary_text = self._format_summary_text(summary)
        self._write_summary_to_log(summary_text)
        print(f"\n{summary_text}\n", flush=True)

    def _write_summary_to_log(self, summary_text: str) -> None:
        log_path = os.path.join(self.run_dir, "unified-benchmark-test.log")
        try:
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(f"Final summary:\n{summary_text}\n")
        except OSError:
            logger.debug("Unable to append summary to log file: %s", log_path)

    def _format_summary_text(self, summary: Dict) -> str:
        overall = summary.get("overall_stats", {})
        by_type = summary.get("by_type", {})

        headers = ["Captcha Type", "Solved", "Total", "Success %", "Avg Steps"]
        rows = []
        for captcha_type, stats in sorted(by_type.items()):
            avg_steps = stats.get("average_solve_steps")
            avg_steps_text = "N/A" if avg_steps is None else f"{avg_steps:.2f}"
            rows.append(
                [
                    captcha_type,
                    str(stats.get("solved_count", 0)),
                    str(stats.get("total_count", 0)),
                    f"{stats.get('success_rate', 0):.2f}",
                    avg_steps_text,
                ]
            )

        col_widths = [len(h) for h in headers]
        for row in rows:
            col_widths = [max(col_widths[i], len(str(row[i]))) for i in range(len(headers))]

        def format_row(values):
            formatted = []
            for idx, value in enumerate(values):
                text = str(value)
                if idx == 0:
                    formatted.append(text.ljust(col_widths[idx]))
                else:
                    formatted.append(text.rjust(col_widths[idx]))
            return "| " + " | ".join(formatted) + " |"

        border = "+-" + "-+-".join("-" * width for width in col_widths) + "-+"
        table_lines = [border, format_row(headers), border]
        table_lines.extend(format_row(row) for row in rows)
        table_lines.append(border)

        summary_line = (
            f"Overall: {overall.get('total_solved', 0)}/"
            f"{overall.get('total_captchas', 0)} solved "
            f"({overall.get('overall_success_rate', 0):.2f}%)"
        )
        average_steps = overall.get("average_solve_steps")
        average_steps_text = "N/A" if average_steps is None else f"{average_steps:.2f}"
        summary_line = f"{summary_line} | Avg steps (solved): {average_steps_text}"
        return "\n".join([*table_lines, summary_line])


def build_run_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
