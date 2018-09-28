#!/usr/bin/python

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class ArmlB1PropShare(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()

    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        pieces_list = []
        pieces_freq = []
        for peer in peers:
            for avp in peer.available_pieces:
                if avp in pieces_list:
                    pieces_freq[pieces_list.index(avp)] += 1
                else:
                    pieces_list.append(avp)
                    pieces_freq.append(1)
        pieces_list1 = sorted(pieces_list, key=lambda x: pieces_freq[pieces_list.index(x)])
        pieces_list_sorted = []
        for p in pieces_list1:
            if p in needed_pieces:
                pieces_list_sorted.append(p)

        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            desired = n
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            if n == len(isect):
                for piece in isect:
                    start_block = self.pieces[piece]
                    r = Request(self.id, peer.id, piece, start_block)
                    requests.append(r)
            else:
                rarity = []
                for piece in isect:
                    rarity.append((piece, pieces_freq[pieces_list.index(piece)]))
                random.shuffle(rarity)
                rarity.sort(key=lambda x: x[1])
                req_pieces = [x[0] for x in rarity[:n]]
                for piece in req_pieces:
                    start_block = self.pieces[piece]
                    r = Request(self.id, peer.id, piece, start_block)
                    requests.append(r)
        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """
        random.shuffle(peers)
        round = history.current_round()
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            chosen = []
            bws = []
        else:
            blocks_up = []
            names = []
            requesters = [x.requester_id for x in requests]
            for up in history.downloads[round - 1]:
                if up.from_id not in names and up.from_id in requesters:
                    names.append(up.from_id)
                    blocks_up.append(up.blocks)
                elif up.from_id in requests:
                    blocks_up[names.index(up.from_id)] += up.blocks
            blocks_tot = sum(blocks_up)
            chosen = []
            bws = []
            for p in peers:
                if p.id in names:
                    chosen.append(p.id)
                    bws.append(int(0.9 * self.up_bw * blocks_up[names.index(p.id)]/blocks_tot))
            random.shuffle(peers)
            for p in peers:
                if p.id not in names:
                    chosen.append(p.id)
                    bws.append(self.up_bw - sum(bws))
                    break
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads
