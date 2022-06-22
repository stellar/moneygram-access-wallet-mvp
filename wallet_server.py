"""
This module is a Flask web server that implements the server side of a very
basic SEP-24 client application. SEP-24 client applications enable their users
to connect to Stellar on & off ramps using banking, mobile money, or cash rails
in the user's region.

This project was built specifically to demonstrate the minimum amount of
development necessary to connect to MoneyGram's SEP-24 server. This code should
not be used in your production environment. It should be used as a reference for
developers to leverage when building this functionality into their own production
systems.
"""

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

#######################################
# Environment Variables / Configuration
#######################################

# USDC for MoneyGram
ASSET_CODE = os.environ.get("STELLAR_ASSET_CODE")

# GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5 for MoneyGram on testnet.
# GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN for MoneyGram on mainnet / pubnet.
ASSET_ISSUER = os.environ.get("STELLAR_ASSET_ISSUER")

# This is the secret key used to sign authentication challenges issued by MoneyGram.
# You should have provided the corresponding public key to MoneyGram as the key
# you will use when requesting an authentication token.
AUTH_STELLAR_KEYPAIR = Keypair.from_secret(os.environ.get("AUTH_SECRET_KEY"))

# This is the secret key of the Stellar account used to send USDC to MoneyGram.
# You should have provided the corresponding public key to MoneyGram.
FUNDS_STELLAR_KEYPAIR = Keypair.from_secret(os.environ.get("FUNDS_SECRET_KEY"))

# GCSESAP5ILVM6CWIEGK2SDOCQU7PHVFYYT7JNKRDAQNVQWKD5YEE5ZJ4 for MoneyGram on testnet.
# GD5NUMEX7LYHXGXCAD4PGW7JDMOUY2DKRGY5XZHJS5IONVHDKCJYGVCL for MoneyGram on mainnet / pubnet.
# This is the public key of the keypair that signs MoneyGrams authentication challenges.
# Client application should use this to ensure the authentication challenges received were
# indeed issued by MoneyGram.
MGI_ACCESS_SIGNING_KEY = os.environ.get("MGI_ACCESS_SIGNING_KEY")

# This is the wallet, exchanges, or application's ID for the user who wants to initiate
# a deposit or withdrawal through MoneyGram. In your production code, this would not be
# a configuration setting.
USER_ID = int(os.environ.get("USER_ID"))

# The base service URL for MoneyGram. All URLs are available at
# https://extstellar.moneygram.com/.well-known/stellar.toml for testnet, and
# https://stellar.moneygram.com/.well-known/stellar.toml for mainnet / pubnet.
# These URLs are taken from those pages.
MGI_ACCESS_BASE_URL = os.environ.get("MGI_ACCESS_BASE_URL")
MGI_ACCESS_HOST = urlparse(MGI_ACCESS_BASE_URL).netloc
MGI_ACCESS_AUTH_URL = f"{MGI_ACCESS_BASE_URL}/auth"
MGI_ACCESS_WITHDRAW_URL = f"{MGI_ACCESS_BASE_URL}/sep24/transactions/withdraw/interactive"
MGI_ACCESS_TRANSACTION_URL = f"{MGI_ACCESS_BASE_URL}/sep24/transaction"

# an in-memory object containing the in-progress or completed transactions. In a production
# system this should be replaced with a database.
transactions = {}

###########
# Endpoints
###########


@app.route("/", methods=["GET"])
def index():
    """
    Returns the HTML page that allows you to initiate transactions and send funds.

    This wallet.html page is a substitute for your business' UI.
    """
    return send_from_directory(".", "wallet.html")


@app.route("/url", methods=["GET"])
def get_url() -> dict:
    """
    The UI (app or browser-based) calls this endpoint to fetch the URL MoneyGram
    provides for a new transaction. This endpoint authenticates with MoneyGram,
    initiates the transaction, then returns the URL and transaction ID to the
    app / browser.
    """
    token = get_token()
    url, txid = initiate_withdraw(token)
    transactions[txid] = {"url": url, "token": token}
    return {"url": url, "txid": txid}


def get_token() -> str:
    """
    This method implements the client-side of SEP-10, the standardized authentication
    API MoneyGram uses to verify that a user or business holds the private key to a
    Stellar account. Think of it as "Sign in with Stellar".

    This method is written from the perspective of a custodian, meaning the business
    manages a set of Stellar accounts and pools their users' funds in these accounts.
    The business should use integer IDs, here used in the 'memo' argument, to identify
    the users of these shared accounts with MoneyGram.

    MoneyGram will use the composite key of (Stellar account, memo ID) to identify the
    user from hereon out, allowing the same user to skip KYC in future transactions
    and view all transactions they've initiated previously.

    SEP-10 is a mutual authentication protocol, meaning both parties verify they are
    interacting with the correct entities. The means of this verification is through
    asymetric encryption & signature checking.

    1. The client (us) requests an authentication challenge
    2. The server (MoneyGram) provides the authentication challenge
    3. The client verifies that MoneyGram signed the authentication with it's SIGNING_KEY
    4. The client signs the authentication challenge with its own key
    5. The client sends the authentication challenge back to the server
    6. The server verifies the client signed the challenge with the account it initially
        used to request the challenge
    7. The server returns a session token for the (account, memo) used in the initial
        authentication request

    SEP-10 protocol specification:
    https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0010.md
    """
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
    """
    This method initiates the cash-out (or withdrawal) transaction. The
    application provides the asset code of the Stellar asset they will be providing,
    the account the payment will be sent from, the language to render the UI in, and
    the amount the user would like to withdrawal.

    Moneygram will return the transaction ID and the URL our application can open for
    the user.
    """
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
    """
    This endpoint is requested when the user has completed the MoneyGram UI
    flow and is ready to send funds for cash-out.

    1. Poll the transaction's status until MoneyGram signals that it is ready to receive funds
    2. Send funds through Stellar to the provided address. Note that the memo MUST be attached
        to the transaction in order for MoneyGram to reconcile the payment with the user's
        initiated transaction.
    3. Poll the transaction's status until MoneyGram has confirmed the receipt of funds. For
        cash-outs, this should occur relatively quickly (5-6 seconds for the transaction to be
        confirmed in a ledger, and another handful of seconds for MoneyGram to detect the
        payment made to their account).
    4. Return the transaction status page ('more_info_url') and reference number to the user
    """
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
    """
    This is a basic polling method that pings the transaction record until
    the transaction's status matches the passed value. Production systems
    should have edge-case handling and bail-out conditions that ensure
    unexpected errors do not pause the flow.
    """
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
    """
    This method constructs a Stellar transaction containing a payment operation
    and submits it to the Stellar network. Production systems should have a much more
    robust function that handles errors and network congestion gracefully. The SDF has
    a documentation page specifically for this:

    https://developers.stellar.org/docs/tutorials/handling-errors/#transaction-submissions

    In short, there are a few things you should do:

    1. Offer a high fee. Your fee should be as high as you would offer before deciding the
        transaction is no longer worth sending. Stellar will only charge you the minimum
        necessary to be included in the ledger -- you won't be charged the amount you offer
        unless everyone else is offering the same amount or greater.
    2. Set a maxmimum timebound on the transaction. This ensures that if your transaction
        is not included in a ledger before the set time, you can reconstruct the transaction
        with a higher offered fee and submit it again with better chances of inclusion.
    3. Resubmit the transaction when you get 504 status codes. 504 status codes are just
        telling you that your transaction is still pending -- not that it has been canceled
        or that your request was invalid. You should simply make the request again with the
        same transaction to get a final status (either included or expired).

    If you use a custodial service, such as Fireblocks, then this logic is abstracted away
    and you would use your custodian's API for sending funds.

    Make sure you add the memo specified by MoneyGram to the transaction, otherwise your
    payment will not be mapped to your transaction initiation request.
    """
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
