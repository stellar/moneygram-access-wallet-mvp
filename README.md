# MoneyGram Access Wallet MVP

This project contains the minimum amount of code necessary to integrate with a [SEP-24](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0024.md) server, specifically [MoneyGram Access](https://stellar.org/moneygram?locale=en).

**THIS CODE SHOULD ONLY BE USED AS A REFERENCE. DO NOT USE THIS CODE IN PRODUCTION.**

## Configuration

The `.env.example` file contains all the environment variables necessary to run the service. The values are configured
for MoneyGram's testing deployment. However, `FUNDS_SECRET_KEY` and `AUTH_SECRET_KEY` should be replaced by keypairs
you generate yourself, either using a Stellar SDK or [Stellar Lab](https://laboratory.stellar.org/#account-creator?network=test).

Copy `.env.example` to `.env`

```shell
$ cp .env.example .env
```

To access MoneyGram's test environment, you will need to contact MoneyGram and provide the public keys associated with `FUNDS_SECRET_KEY` and `AUTH_SECRET_KEY`. They will add these public keys to a list of known accounts.

## Running

The project can be run locally using Docker Compose.

```shell
$ docker compose up
```

You should be able to access the UI at http://localhost:5000. Adjusting the code should automatically restart the docker container.

### Running Without Docker

You'll need to export the variables from the `.env` file to the environment running the web server. You can do this line-by-line, or try exporting all environment variables in the file. This [StackOverflow post](https://stackoverflow.com/questions/19331497/set-environment-variables-from-file-of-key-value-pairs) may be helpful. Then:

```shell
$ poetry install
$ poetry run python wallet_server.py
```
