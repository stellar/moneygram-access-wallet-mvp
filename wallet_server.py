import os
import time
import json
from urllib.parse import urlparse
from typing import Tuple

import requests
from flask import Flask, request, send_from_directory
from flask_cors import CORS
from stellar_sdk import Keypair, Network, TransactionBuilder, Server, Asset, IdMemo
from stellar_sdk.sep.stellar_web_authentication import read_challenge_transaction

app = Flask(__name__, static_url_path='', static_folder=".")
CORS(app)

ASSET_CODE = os.environ.get("STELLAR_ASSET_CODE")
ASSET_ISSUER = os.environ.get("STELLAR_ASSET_ISSUER")
AUTH_STELLAR_KEYPAIR = Keypair.from_secret(os.environ.get("AUTH_SECRET_KEY"))
FUNDS_STELLAR_KEYPAIR = Keypair.from_secret(os.environ.get("FUNDS_SECRET_KEY"))
MGI_ACCESS_SIGNING_KEY = os.environ.get("MGI_ACCESS_SIGNING_KEY")
USER_ID = int(os.environ.get("USER_ID"))

MGI_ACCESS_BASE_URL = os.environ.get("MGI_ACCESS_BASE_URL")
MGI_ACCESS_HOST = urlparse(MGI_ACCESS_BASE_URL).netloc
MGI_ACCESS_AUTH_URL = f"{MGI_ACCESS_BASE_URL}/auth"
MGI_ACCESS_WITHDRAW_URL = f"{MGI_ACCESS_BASE_URL}/sep24/transactions/withdraw/interactive"
MGI_ACCESS_TRANSACTION_URL = f"{MGI_ACCESS_BASE_URL}/sep24/transaction"

transactions = {}


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(".", "wallet.html")


@app.route("/url", methods=["GET"])
def get_url() -> dict:
    token = get_token()
    url, txid = initiate_withdraw(token)
    transactions[txid] = {"url": url, "token": token}
    return {"url": url, "txid": txid}


def get_token() -> str:
    query = f"{MGI_ACCESS_AUTH_URL}?account={AUTH_STELLAR_KEYPAIR.public_key}&memo={USER_ID}"
    app.logger.info(f"making request: GET {query}")
    response = requests.get(query)
    body = response.json()
    app.logger.info(f"response: {json.dumps(body)}")
    challenge = read_challenge_transaction(
        challenge_transaction=body["transaction"],
        server_account_id=MGI_ACCESS_SIGNING_KEY,
        home_domains=MGI_ACCESS_HOST,
        web_auth_domain=MGI_ACCESS_HOST,
        network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE
    )
    challenge.transaction.sign(AUTH_STELLAR_KEYPAIR)
    post_body = {
        "transaction": challenge.transaction.to_xdr()
    }
    app.logger.info(f"making request: POST {MGI_ACCESS_AUTH_URL} {json.dumps(post_body)}")
    response = requests.post(f"{MGI_ACCESS_AUTH_URL}", json=post_body)
    response_body = response.json()
    app.logger.info(f"response: {json.dumps(response_body)}")
    return response_body["token"]


def initiate_withdraw(token: str) -> Tuple[str, str]:
    post_body = {
        "asset_code": ASSET_CODE,
        "account": FUNDS_STELLAR_KEYPAIR.public_key,
        "lang": "en",
        "amount": "10"
    }
    app.logger.info(f"making request: POST {MGI_ACCESS_WITHDRAW_URL} {json.dumps(post_body)}")
    response = requests.post(
        MGI_ACCESS_WITHDRAW_URL,
        json=post_body,
        headers={
            "Authorization": f"Bearer {token}"
        }
    )
    body = response.json()
    app.logger.info(f"response: {json.dumps(body)}")
    return body["url"] + "&callback=postmessage", body["id"]


@app.route("/send", methods=["POST"])
def send() -> dict:
    data = request.get_json()
    body = poll_transaction_until_status(data["id"], "pending_user_transfer_start")
    submit_payment(
        txid=data['id'],
        destination=body["transaction"]["withdraw_anchor_account"],
        memo=body["transaction"]["withdraw_memo"],
        amount=body["transaction"]["amount_in"]
    )
    body = poll_transaction_until_status(data["id"], "pending_user_transfer_complete")
    return {
        "status": "ok",
        "url": body["transaction"]["more_info_url"],
        "refNumber": body["transaction"]["external_transaction_id"]
    }


def poll_transaction_until_status(txid: str, until_status: str) -> dict:
    first_iteration = True
    response_body = None
    status = None
    while status != until_status:
        if first_iteration:
            time.sleep(1)
            first_iteration = False
        query = f"{MGI_ACCESS_TRANSACTION_URL}?id={txid}"
        app.logger.info(f"making request: GET {query}")
        response = requests.get(
            query,
            headers={
                "Authorization": f"Bearer {transactions[txid]['token']}"
            }
        )
        response_body = response.json()
        status = response_body["transaction"]["status"]
    return response_body


def submit_payment(txid: str, destination: str, memo: str, amount: str):
    server = Server()
    account = server.load_account(FUNDS_STELLAR_KEYPAIR.public_key)
    transaction = TransactionBuilder(
        source_account=account,
        network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
        base_fee=10000
    ).append_payment_op(
        destination=destination,
        asset=Asset(ASSET_CODE, ASSET_ISSUER),
        amount=amount,
    ).add_memo(
        IdMemo(int(memo))
    ).build()
    transaction.sign(FUNDS_STELLAR_KEYPAIR)
    app.logger.info(f"submitting transaction {transaction.to_xdr()} ...")
    response = server.submit_transaction(transaction)
    app.logger.info(f"response: {json.dumps(response)}")
    transactions[txid]["hash"] = response["id"]


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
