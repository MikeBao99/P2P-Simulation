#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class ArmlB1Tyrant(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"

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


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)

        # Sort peers by id.  This is probably not a useful sort, but other
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in random.sample(isect, n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
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
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
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
            # print(rat)
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
            # request = random.choice(requests)
            # chosen.append(request.requester_id)
            # bws.append(self.up_bw - sum(bws))
            # request = random.choice(requests)
            # chosen = [request.requester_id]
            # Evenly "split" my upload bandwidth among the one chosen requester

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
        # print(t)
        return uploads
