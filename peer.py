#!/usr/bin/python

import random
from messages import Upload, Request
from util import even_split

class Peer:
    def __init__(self, config, id, init_pieces, up_bandwidth):
        self.conf = config
        self.id = id
        self.pieces = init_pieces[:]
        # bandwidth measured in blocks-per-time-period
        self.up_bw = up_bandwidth

        # This is an upper bound on the number of requests to send to
        # each peer -- they can't possibly handle more than this in one round
        self.max_requests = self.conf.max_up_bw / self.conf.blocks_per_piece + 1
        self.max_requests = min(self.max_requests, self.conf.num_pieces)

        self.post_init()

    def __repr__(self):
        return "%s(id=%s pieces=%s up_bw=%d)" % (
            self.__class__.__name__,
            self.id, self.pieces, self.up_bw)

    def update_pieces(self, new_pieces):
        """
        Called by the sim when this peer gets new pieces.  Using a function
        so it's easy to add any extra processing...
        """
        self.pieces = new_pieces

    def requests(self, peers, history):
        return []

    def uploads(self, requests, peers, history):
        return []

    def post_init(self):
        # Here to be overridden by child classes
        pass
