#!/usr/bin/env python3
"""
Script de configuración OAuth2 para Gmail
Genera token.pickle para acceso a Gmail API
"""

import os
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def setup_gmail():
    creds = None
    token_file = "/Users/ramonesnaola/URA/ura_ia_1972/token.pickle"
    credentials_file = "/Users/ramonesnaola/URA/ura_ia_1972/credentials.json"

    if os.path.exists(token_file):
        with open(token_file, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refrescando token expirado...")
            creds.refresh(Request())
        else:
            print("🔐 Iniciando flujo OAuth2...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, "wb") as token:
            pickle.dump(creds, token)

    print("✅ Autenticación completada. Token guardado en token.pickle")
    print("📧 URA ahora puede leer tus correos de Gmail")
    return creds


if __name__ == "__main__":
    setup_gmail()
