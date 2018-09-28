#!/usr/bin/python

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class ArmlB1Tyrant(Peer):
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

        requests = []
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
        # Sort peers by id.  This is probably not a useful sort, but other
        # sorts might be useful
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
        gamma = 0.10
        r = 3
        alpha = 0.20
        # unchoke three agents every round
        k = 3
        random.shuffle(peers)
        random.shuffle(requests)
        name = [p.id for p in peers]
        f = [((self.conf.max_up_bw + self.conf.min_up_bw) / 2.0 ) / len(peers)] * len(peers)
        t = [((self.conf.max_up_bw + self.conf.min_up_bw) / 2.0 ) / 3] * len(peers)
        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.
        if len(requests) == 0:
            chosen = []
            bws = []
        else:
            unchoked = set([x.to_id for x in history.uploads[round - 1]])
            if round - 2 >= 0:
                unchoked1 = set([x.to_id for x in history.uploads[round - 2]])
            else:
                unchoked1 = []
            if round - 3 >= 0:
                unchoked2 = set([x.to_id for x in history.uploads[round - 3]])
            else:
                unchoked2 = []
            ups = set([x.from_id for x in history.downloads[round - 1]])
            for unc in unchoked:
                indx = name.index(unc)
                if unc not in ups:
                    t[indx] *= (1 + alpha)
                else:
                    rate = 0
                    for x in history.downloads[round - 1]:
                        if x.to_id == unc:
                            rate += x.blocks
                    f[indx] = rate
                if unc in unchoked and unc in unchoked1 and unc in unchoked2:
                    t[indx] *= (1 - gamma)
            up_bw = self.up_bw
            rat = [float(x)/y for (x,y) in zip(f, t)]
            rat = sorted(range(len(f)), key= lambda s: rat[s])
            rat = rat[::-1]
            i = 0
            chosen = []
            bws = []
            requesters = [x.requester_id for x in requests]
            while i < len(rat) and up_bw >= t[i]:
                if name[i] in requesters:
                    chosen.append(name[i])
                    bws.append(t[i])
                    up_bw -= t[i]
                i += 1

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
        return uploads
