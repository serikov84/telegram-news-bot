"""
Одноразовый локальный помощник для получения LinkedIn access/refresh token
через OAuth 2.0 (Authorization Code flow).

ВАЖНО: запускать ЛОКАЛЬНО на своей машине (не в облачной сессии/консоли) —
скрипт открывает браузер для логина в LinkedIn и должен принять редирект
на localhost.

Использование — запустить дважды, с разным --scope, под нужным логином:

    # токен для личного профиля (постинг от своего имени)
    python scripts/linkedin_auth.py --scope "openid profile email w_member_social"

    # токен для страницы компании aiu (нужны права админа страницы у аккаунта,
    # под которым логинитесь; логин может быть тот же самый)
    python scripts/linkedin_auth.py --scope "w_organization_social rw_organization_admin"

Точные названия scope смотрите на вкладке Auth вашего приложения в LinkedIn
Developer Portal — они зависят от того, какие Products были одобрены, и могут
отличаться от значений по умолчанию выше.

Перед запуском задайте переменные окружения (можно через .env в корне репо):
    LINKEDIN_CLIENT_ID=...
    LINKEDIN_CLIENT_SECRET=...

Redirect URI жёстко задан как http://localhost:8080/callback — он должен быть
добавлен в настройках приложения (вкладка Auth) один в один, включая порт.

Результат (access_token, refresh_token, сроки жизни) печатается в терминал —
скопируйте их в .env вручную. Скрипт ничего никуда не отправляет и не сохраняет.
"""

import argparse
import http.server
import os
import secrets
import threading
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

load_dotenv()

REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

_result = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _result["code"] = params.get("code", [None])[0]
        _result["state"] = params.get("state", [None])[0]
        _result["error"] = params.get("error_description", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if _result.get("code"):
            self.wfile.write("<h2>Готово, можно закрыть вкладку и вернуться в терминал.</h2>".encode())
        else:
            self.wfile.write(f"<h2>Ошибка: {_result.get('error')}</h2>".encode())

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        required=True,
        help='Список scope через пробел, напр. "openid profile email w_member_social"',
    )
    args = parser.parse_args()

    client_id = os.environ["LINKEDIN_CLIENT_ID"]
    client_secret = os.environ["LINKEDIN_CLIENT_SECRET"]
    state = secrets.token_urlsafe(16)

    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": args.scope,
        "state": state,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    server = http.server.HTTPServer(("localhost", 8080), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print("Открываю браузер для логина в LinkedIn...")
    print("Если не открылся автоматически, перейдите по ссылке:\n", url, "\n")
    webbrowser.open(url)

    thread.join()
    server.server_close()

    if _result.get("state") != state:
        raise SystemExit("state не совпал с ожидаемым — повторите запуск заново.")
    if not _result.get("code"):
        raise SystemExit(f"Не получен code от LinkedIn: {_result.get('error')}")

    token_resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": _result["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    token_resp.raise_for_status()
    data = token_resp.json()

    print("\n=== Результат (сохраните в .env) ===")
    print("access_token:", data.get("access_token"))
    print("expires_in (сек):", data.get("expires_in"))
    if "refresh_token" in data:
        print("refresh_token:", data.get("refresh_token"))
        print("refresh_token_expires_in (сек):", data.get("refresh_token_expires_in"))
    else:
        print(
            "refresh_token не выдан — либо продукт Programmatic Refresh Tokens "
            "не одобрен для приложения, либо он не нужен для этого scope."
        )


if __name__ == "__main__":
    main()
