import hashlib
import json
from time import time

from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request

# Build a blockchain site
# https://blockchain.works-hub.com/learn/Learn-Blockchains-by-Building-One


# GET requests
"""
http://localhost:5000/mine
http://localhost:5000/chain
http://localhost:5000/nodes/resolve
"""

# POST requests (not working)
"""
http://localhost:5000/transactions/new
http://localhost:5000/nodes/register
"""


class Blockchain:

    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()

        # Genesis block
        self.new_block(prev_hash='1', proof=100)

    def register_node(self, addr):
        """
        Add a new node to the list of nodes
        :param addr: Address of node. Eg. 'http://192.168.0.5:5000'
        """

        parse_url = urlparse(addr)
        if parse_url.netloc:
            self.nodes.add(parse_url.netloc)
        elif parse_url.path:
            # Accepts URL without scheme like 'http://192.168.0.5:5000'
            self.nodes.add(parse_url.path)
        else:
            raise ValueError('Invalid URL')

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid
        :param chain: A blockchain
        :return: True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Check that the hash of the block is correct
            last_block_hash = self.hash(last_block)
            if block['previous_hash'] != last_block_hash:
                return False

            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof'], last_block_hash):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        This is our consensus algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.
        :return: True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, prev_hash):

        block = {
            'prev_hash': prev_hash,
            'proof': proof,
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transaction': self.current_transactions,
        }

        # Reset c_t
        self.current_transactions = []
        # Add block to chain
        self.chain.append(block)
        return block

    def new_transaction(self, sender, receiver, amount, team):
        '''
        Creates transaction to go into next created/mined block
        :param sender: Address of the Sender
        :param recipient: Address of the Recipient
        :param amount: Amount
        :param team: team sender is 'betting' on  ---- Could do HOME/AWAY bool
        :return: Index of block that holds transaction
        '''

        self.current_transactions.append({
            'sender': sender,
            'receiver': receiver,
            'amount': amount,
            'team': team,
        })

        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a Block
        :param block: Block
        """

        # Dictionary needs to be ordered for chain to work - inconsistent hashes
        block_str = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_str).hexdigest()

    def proof_of_work(self, last_block):
        '''
        PoW how new blocks are created/mined on the blockchain
        Should be difficult to find to be easy to verify

        PoW Algorithm
            - Find a number p' such that hash(pp') first 4 digits are 0's
            - WHere p is prev proof and p' in new proof
        '''

        last_proof = last_block['proof']
        last_hash = self.hash(last_block)

        proof = 0
        while self.valid_proof(last_proof, proof, hash) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        """
        Validates the Proof
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :param last_hash: <str> The hash of the Previous Block
        :return: <bool> True if correct, False if not.
        """

        guess = f'{last_hash}{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexidegest()

        return guess_hash[:4] == '0000'


# Instantiate our Node
app = Flask(__name__)

# Generate globally unique addr for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain class
blockchain = Blockchain()

# Creates mine endpoint  -  GET request
@app.route('/mine', methods=['GET'])
def mine():
    """
    - Needs to calculate PoW
    - Grant miner 1 coin for finding proof
    - Add new block to chain
    """

    # Run PoW algorithm to get next proof
    last_block = blockchain.last_block
    #last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_block)

    # Receive coin for finding proof
    # Sender is '0' as node has mined new coin
    blockchain.new_transaction(
        sender='0',
        receiver=node_identifier,
        amount=1,
        team=input(),
    )

    # Forge new block by adding it to the chain
    prev_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'prev_hash': block['prev_hash'],
    }

    return jsonify(response), 200

# Create transactions/new endpoint  -  POST request (sending data to it)
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json(force=True)

    # Check required fields are in the POSTed data
    required = ['sender', 'receiver', 'amount', 'team']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create new transaction
    index = blockchain.new_transaction(values['sender'], values['receiver'], values['amount'], values['team'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


# Chain endpoint returns the full blockchain
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)