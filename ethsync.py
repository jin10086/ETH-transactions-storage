# Indexer for Ethereum to get transaction list by ETH address
# https://github.com/Adamant-im/ETH-transactions-storage
# By Artem Brunov, Aleksei Lebedev. (c) ADAMANT TECH LABS
# v. 1.1

from web3.auto import w3
from web3 import HTTPProvider, Web3, WebsocketProvider
from web3.middleware import geth_poa_middleware

from pymongo import MongoClient
from loguru import logger
import json
import os

if os.environ.get("USEBSC"):
    logger.info("使用bsc官方节点.")
    w3 = Web3(
        HTTPProvider("https://bsc-dataseed.binance.org", request_kwargs={"timeout": 60})
    )
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

logger.add(
    "ethsync.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss:SSS} - {level} - {file} - {line} - {message}",
    rotation="10 MB",
)

client = MongoClient()["ethtx"]["txlist"]

# Adds all transactions from Ethereum block
def insertion(blockid, tr):
    logger.info(f"insert: {blockid}")
    wait_insert = []
    for x in range(0, tr):
        trans = w3.eth.getTransactionByBlock(blockid, x)
        txhash = trans["hash"].hex()
        value = str(trans["value"])
        inputinfo = trans["input"]
        fr = trans["from"]
        to = trans["to"]
        gasprice = str(trans["gasPrice"])
        _txinfo = w3.eth.getTransactionReceipt(trans["hash"])
        gas = str(_txinfo["gasUsed"])
        status = _txinfo["status"]
        logs = _txinfo["logs"]
        _insert = {
            "txhash": txhash,
            "value": value,
            "inputinfo": inputinfo,
            "fr": fr,
            "to": to,
            "gasprice": gasprice,
            "gas": gas,
            "status": status,
            "logs": json.loads(w3.toJSON(logs)),
            "block": blockid,
        }
        wait_insert.append(_insert)
    client.insert_many(wait_insert)


def gettx(txhash):
    return client.find_one({"txhash": txhash})


def getblock(blockid):
    return list(client.find({"block": blockid}))


def getAccountTx(fr, blockid, qlimit=100000, returnlogs=0):
    return list(client.find(
        {"fr": fr, "block": {"$gt": blockid}},
        {"logs": returnlogs, "_id": 0},
        sort=[("block", -1)],
    ).limit(qlimit))


if __name__ == "__main__":
    while True:
        maxblockindb = client.find_one(sort=[("block", -1)])
        if not maxblockindb:
            maxblockindb = 5500000
        else:
            maxblockindb = maxblockindb["block"]
        endblock = int(w3.eth.blockNumber)
        logger.info(
            "Current best block in index: "
            + str(maxblockindb)
            + "; in Ethereum chain: "
            + str(endblock)
        )
        for block in range(maxblockindb + 1, endblock):
            transactions = w3.eth.getBlockTransactionCount(block)
            if transactions > 0:
                insertion(block, transactions)
            else:
                logger.info("Block " + str(block) + " does not contain transactions")
