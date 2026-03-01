# Dynamic CAPTCHAs

`dynamic_captchas` is a Flask server that generates unlimited interactive CAPTCHA with randomized layouts/styles and server-side verification. This is part of the ReCAP project.

## 🚀 Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

It is advised to use a virtual environment to avoid conflicts with existing packages.

### Dataset Setup

The server expects three datasets:

1. Text CAPTCHA dataset from Hugging Face: `yuxi5/captcha-data-clean`, a cleanup version based on `hammer888/captcha-data`.
2. reCAPTCHA category images from Kaggle: `mikhailma/test-dataset`
3. Background images from Kaggle: `nguyenquocdungk16hl/bg-20o`

All datasets can be automatically downloaded and prepared using `download_datasets.py` script. The script handles downloading, extraction, and organization of datasets into the expected directory structure under `data/`.

```bash
python download_datasets.py
```

You may be prompted for kaggle API token if not set in the environment. For more details on Kaggle API token setup, please see [Kaggle Public API Documentation](https://www.kaggle.com/docs/api).

### Start Server

After setting up the environment and datasets, you can start the Flask server. You can specify the port by setting the `PORT` environment variable (default is 5000):

```bash
python app.py # default port 5000
PORT=8000 python app.py # with custom port
```

## ✨ Server API

### API Endpoints

- `GET /challenge` -> random challenge page
- `GET /challenge/static` -> deterministic static sequence
- `GET /challenge/<type>` -> specific challenge type page
    - Text CAPTCHA (`/challenge/text`)
    - Compact Text CAPTCHA (`/challenge/compact`)
    - Icon selection CAPTCHA (`/challenge/icon`)
    - Paged CAPTCHA (`/challenge/paged`)
    - Slider CAPTCHA (`/challenge/slider`)
    - Image Grid CAPTCHA (`/challenge/image_grid`)
    - Icon Match CAPTCHA (`/challenge/icon-match`)
- `POST /verify` -> verify user submission
- `GET /status/<challenge_id>` -> challenge status metadata
- `GET /solution/<challenge_id>` -> expected answer/solution payload

### Dataset Split Behavior

We provide a deterministic static sequence of challenges for testing and benchmarking purposes at `/challenge/static`, which includes differnt CAPTCHA types in a fixed order. The server reserves a small portion of datasets for the static endpoint to avoid data leakage. Specifically:

- `/challenge/static` uses `dataset_scope="static"`
- all other challenge endpoints use `dataset_scope="dynamic"`

### Verification Behavior

The server performs server-side verification of user submissions against the expected solution. The '/verify' endpoint accepts user responses and returns a JSON response indicating success or failure. The expected solution for each challenge is stored server-side and can be retrieved via the `/solution/<challenge_id>` endpoint for testing and verification purposes.

## 🏗 Project Layout

```text
dynamic_captchas/
├── app.py
├── server/
│   ├── __init__.py
│   ├── routes.py
│   └── challenge_manager.py
├── challenges/
│   ├── dataset.py
│   ├── text.py
│   ├── icon.py
│   ├── paged.py
│   ├── slider.py
│   ├── image_grid.py
│   ├── icon_match.py
│   └── common.py
├── assets/
│   ├── css/
│   ├── js/
│   └── template/
├── download_datasets.py
├── requirements.txt
└── data/
    ├── text_captcha/
    ├── recaptchav2/images/
    └── backgrounds/
```
