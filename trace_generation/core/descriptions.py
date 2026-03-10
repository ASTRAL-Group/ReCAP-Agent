from typing import Dict


def describe_challenge(challenge_type: str, solution_data) -> str:
    if isinstance(solution_data, str) and challenge_type in {"text", "compact_text"}:
       solution = solution_data
    else:
       solution = solution_data.get("solution")

    if challenge_type == "compact_text":
        if solution:
            return f"The text CAPTCHA shows distorted characters that resolve to '{solution}'."
        return "The text CAPTCHA asks for the transcribed characters shown in the image."

    if challenge_type == "text":
        if solution:
            return f"The text CAPTCHA displays warped letters that read '{solution}'."
        return "The text CAPTCHA requires typing the letters shown in the image."

    if challenge_type == "icon_selection":
        target_icon = solution_data.get("target_icon") or solution_data.get("target_icon_name") or solution
        if target_icon:
            return f"The icon selection challenge requests clicking the tile that shows a '{target_icon}'."
        return "The icon selection challenge requires clicking the tile that matches the requested icon."

    if challenge_type == "paged":
        target_icon = solution_data.get("target_icon") or solution_data.get("target_icon_name") or solution
        mode = solution_data.get("mode") or solution_data.get("data_source")
        target_category = solution_data.get("target_category") or target_icon
        total_cards = solution_data.get("total_cards") or (len(solution_data.get("card_icons", [])) if isinstance(solution_data.get("card_icons"), list) else None)
        if mode == "category_image":
            if target_category and total_cards:
                return (
                    f"The paged challenge cycles through {total_cards} photo cards; slide until you find "
                    f"the card from the '{target_category}' category and submit."
                )
            if target_category:
                return (
                    "The paged challenge presents a carousel of category images. "
                    f"Slide through the cards until you see '{target_category}', then submit the choice."
                )
            return "The paged challenge shows one card at a time; navigate the carousel to locate the requested category image and submit."
        if target_icon and total_cards:
            return (
                f"The paged challenge cycles through {total_cards} cards; you must slide until you find "
                f"the card showing '{target_icon}' and then submit."
            )
        if target_icon:
            return (
                f"The paged challenge presents a carousel of cards. Slide through them until you see "
                f"'{target_icon}', then submit the choice."
            )
        return "The paged challenge shows one card at a time; navigate the carousel to locate the requested icon and submit."

    if challenge_type == "icon_match":
        pair_icon = solution_data.get("pair_icon") or solution_data.get("pair_icon_name") or solution_data.get(
            "pair_icon_label", ""
        )
        if pair_icon:
            return (
                "The icon match challenge scatters multiple symbols on a canvas, including two identical "
                f"'{pair_icon}' icons that must be dragged together."
            )
        return (
            "The icon match challenge scatters multiple icons on a canvas and requires dragging the twin icons "
            "on top of one another."
        )

    if challenge_type == "slider":
        try:
            target_position = float(solution_data.get("solution", 0.0))
            track_width = float(solution_data.get("track_width", 0.0))
        except (TypeError, ValueError):
            target_position = 0.0
            track_width = 0.0
        ratio = (target_position / track_width) if track_width else 0.0
        piece_size = solution_data.get("piece_size")
        puzzle_width = solution_data.get("puzzle_width")
        # slider_size = solution_data.get("slider_size")
        piece_pct = None
        if piece_size and puzzle_width:
            try:
                piece_pct = float(piece_size) / float(puzzle_width) if float(puzzle_width) else None
            except (TypeError, ValueError):
                piece_pct = None

        description_parts = ["The puzzle slider shows a scenic background with a missing piece."]
        if piece_pct:
            description_parts.append(f"The loose piece spans roughly {piece_pct:.0%} of the scene width.")
        # if slider_size:
        #     try:
        #         slider_size_val = float(slider_size)
        #         description_parts.append(f"The draggable handle is about {slider_size_val:.0f}px wide.")
        #     except (TypeError, ValueError):
        #         pass
        if ratio:
            description_parts.append(f"The gap aligns about {ratio:.0%} across the track.")
        description_parts.append("Drag the slider until the piece snaps into place.")
        return " ".join(description_parts)

    if challenge_type == "image_grid":
        instruction = solution_data.get("instruction") or solution_data.get("target_category", "")
        tiles = solution_data.get("correct_tiles")
        tile_list = ", ".join(str(idx) for idx in tiles) if isinstance(tiles, list) and tiles else ""
        requires_selection = bool(tiles)

        if instruction and requires_selection:
            detail = f" The correct tile indices are {tile_list}." if tile_list else ""
            return (
                "The image-grid challenge opens a 3x3 tile panel and asks to select each tile that matches "
                f"'{instruction}'.{detail}"
            )
        if instruction and not requires_selection:
            return (
                "The image-grid challenge opens a tile panel asking for "
                f"'{instruction}', but no tiles need to be selected before verification."
            )
        if requires_selection:
            detail = f" Select tile indices {tile_list} before verification." if tile_list else " Select the highlighted tiles before verification."
            return "The image-grid challenge opens a tile grid." + detail
        return "The image-grid challenge opens a tile grid, but no selections are required before verification."

    return "The challenge requires interacting with the on-screen controls to solve the CAPTCHA."


def describe_actions(challenge_type: str, solution_data: Dict) -> str:
    if challenge_type in {"text", "compact_text"}:
        return "Focus the input field, type the recognized characters exactly, then press submit."

    if challenge_type == "icon_selection":
        target_icon = solution_data.get("solution") or solution_data.get("target_icon", "")
        requires_submit = solution_data.get("requires_submit")
        if target_icon:
            if requires_submit is False:
                return f"Click the tile depicting '{target_icon}' and let the challenge auto-submit."
            return f"Select the tile depicting '{target_icon}' and confirm the choice."
        if requires_submit is False:
            return "Click the requested tile and wait for the automatic submission."
        return "Select the requested tile and confirm the choice."

    if challenge_type == "paged":
        target_icon = solution_data.get("solution") or solution_data.get("target_icon", "")
        target_category = solution_data.get("target_category") or target_icon
        mode = solution_data.get("mode") or solution_data.get("data_source")
        total_cards = solution_data.get("total_cards") or (
            len(solution_data.get("card_icons", [])) if isinstance(solution_data.get("card_icons"), list) else None
        )
        card_detail = f" through {total_cards} cards" if total_cards else ""
        current_icon = solution_data.get("current_card_icon")
        matched = solution_data.get("matched")
        if matched is None and current_icon and target_icon:
            matched = current_icon == target_icon
        if matched:
            if mode == "category_image":
                target_label = target_category or target_icon
                if target_label:
                    return f"The target card '{target_label}' is already visible, so submission is required now."
                return "The target card is already visible, so submission is required now."
            if target_icon:
                return f"The '{target_icon}' card is already visible, so submission is required now."
            return "The target card is already visible, so submission is required now."
        if mode == "category_image":
            if target_category:
                return (
                    f"Use the navigation arrows to slide{card_detail} until a card from '{target_category}' is visible, then press submit."
                )
            return f"Slide the carousel{card_detail} until the requested category image is visible, then submit."
        if target_icon:
            return f"Use the navigation arrows to slide{card_detail} until '{target_icon}' is visible, then press submit."
        return f"Slide the carousel{card_detail} until the requested icon is visible, then submit."

    if challenge_type == "icon_match":
        pair_icon = solution_data.get("pair_icon") or solution_data.get("pair_icon_name", "")
        detail = f"the two '{pair_icon}' icons" if pair_icon else "the matching pair"
        return (
            f"Pick up one of {detail} on the canvas, drag it directly over its twin, and release to finish verification."
        )

    if challenge_type == "slider":
        requires_submit = solution_data.get("requires_submit")
        base = "Glide the circular handle until the puzzle piece locks into the cutout"
        if requires_submit is False:
            return base + ", then release to let the page auto-submit."
        return base + ", then press submit."

    if challenge_type == "image_grid":
        tiles = solution_data.get("correct_tiles")
        instruction = solution_data.get("instruction") or solution_data.get("target_category", "")
        if isinstance(tiles, list):
            if tiles:
                tile_list = ", ".join(str(idx) for idx in tiles)
                if instruction:
                    return (
                        f"Open the image grid, click tiles {tile_list} that match '{instruction}', then press verify."
                    )
                return f"Open the image grid, click tiles {tile_list}, then press verify."
            base = "Open the image grid, confirm no tiles should be selected"
            if instruction:
                base += f" for '{instruction}'"
            return base + ", then press verify."
        if instruction:
            return f"Open the image grid, click tiles that match '{instruction}', and click verify."
        return "Open the image grid, click each correct tile, and click verify."

    return "Follow the interaction steps required to satisfy the CAPTCHA and submit."


def default_reasoning(challenge_type: str, solution_data: Dict) -> str:
    if challenge_type == "compact_text":
        return "Thinking: I'll enter the characters shown in the compact text CAPTCHA image and submit the answer."

    if challenge_type == "text":
        return "Thinking: I'll enter the characters shown in the text CAPTCHA image and submit the answer."

    if challenge_type == "icon_selection":
        target_icon = solution_data.get("solution") or solution_data.get("target_icon", "the requested icon")
        if solution_data.get("requires_submit") is False:
            return f"Thinking: I'll click the tile showing '{target_icon}' on the canvas and let the page submit automatically."
        return f"Thinking: I'll click the tile showing '{target_icon}' on the canvas and then submit the selection."

    if challenge_type == "paged":
        target_icon = solution_data.get("solution") or solution_data.get("target_icon", "the requested icon")
        target_category = solution_data.get("target_category") or target_icon
        mode = solution_data.get("mode") or solution_data.get("data_source")
        total_cards = solution_data.get("total_cards") or (
            len(solution_data.get("card_icons", [])) if isinstance(solution_data.get("card_icons"), list) else None
        )
        step_hint = ""
        matched = solution_data.get("matched")
        if total_cards:
            try:
                current_idx = int(solution_data.get("current_card_index", 0))
                current_icon = solution_data.get("current_card_icon") or "current card"
                base_hint = (
                    f"Currently on card {current_idx + 1} of {total_cards} showing '{current_icon}'. "
                )
                if matched is False:
                    step_hint = base_hint + "This is not the target, so I'll move to the next card. "
                elif matched:
                    step_hint = base_hint + "This matches the target, so I'll submit. "
                else:
                    step_hint = base_hint + "I'll advance to the next card until the target appears. "
            except (TypeError, ValueError):
                step_hint = f"There are {total_cards} cards to cycle through. "
        target_label = target_category if mode == "category_image" else target_icon
        action_phrase = (
            f"I'll click the next arrow until the card from '{target_label}' is visible, then press submit."
            if mode == "category_image"
            else f"I'll click the next arrow until the '{target_label}' card is visible, then press submit."
        )
        return (
            "Thinking: " + step_hint +
            action_phrase
        )

    if challenge_type == "icon_match":
        pair_icon = solution_data.get("pair_icon") or solution_data.get("pair_icon_name", "the matching icons")
        return (
            "Thinking: I'll grab one copy of "
            f"'{pair_icon}' on the canvas, drag it so it overlaps perfectly with its twin, and wait for the "
            "auto-verification message."
        )

    if challenge_type == "slider":
        if solution_data.get("requires_submit") is False:
            return (
                f"Thinking: I'll guide the slider so the puzzle piece settles cleanly into the missing slot and let the interface auto-submit once I release."
            )
        return (
            f"Thinking: I'll guide the slider so the puzzle piece settles cleanly into the missing slot and then submit the attempt."
        )

    if challenge_type == "image_grid":
        instruction = solution_data.get("instruction") or solution_data.get("target_category", "the requested object")
        tiles = solution_data.get("correct_tiles")
        if isinstance(tiles, list):
            if tiles:
                tile_list = ", ".join(str(idx) for idx in tiles)
                return (
                    "Thinking: I'll open the image-grid challenge, inspect the tiles for the requested concept, "
                    f"click tiles {tile_list} that show '{instruction}', and press verify."
                )
            return (
                "Thinking: I'll open the image-grid challenge, confirm none of the tiles show "
                f"'{instruction}', and press verify without selecting any."
            )
        return (
            "Thinking: I'll open the image-grid challenge, select each tile showing "
            f"'{instruction}', and press verify."
        )

    return "Thinking: I'll follow the required steps to solve this CAPTCHA and submit the result."
