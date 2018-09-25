#!/usr/bin/python

import copy
import pprint


class AgentHistory:
    """
    History available to a single peer

    history.downloads: [[Download objects for round]]  (one sublist for each round)
         All the downloads _to_ this agent.
        
    history.uploads: [[Upload objects for round]]  (one sublist for each round)
         All the downloads _from_ this agent.

    """
    def __init__(self, peer_id, downloads, uploads):
        """
        Pull out just the info for peer_id.
        """
        self.uploads = uploads
        self.downloads = downloads
        self.peer_id = peer_id

    def last_round(self):
        return len(self.downloads)-1

    def current_round(self):
        """ 0 is the first """
        return len(self.downloads)

    def __repr__(self):
        return "AgentHistory(downloads=%s, uploads=%s)" % (
            pprint.pformat(self.downloads),
            pprint.pformat(self.uploads))


class History:
    """History of the whole sim"""
    def __init__(self, peer_ids, upload_rates):
        """
        uploads:
                   dict : peer_id -> [[uploads] -- one list per round]
        downloads:
                   dict : peer_id -> [[downloads] -- one list per round]
                   
        Keep track of the uploads _from_ and downloads _to_ the
        specified peer id.
        """
        self.upload_rates = upload_rates  # peer_id -> up_bw
        self.peer_ids = peer_ids[:]

        self.round_done = dict()   # peer_id -> round finished
        self.downloads = dict((pid, []) for pid in peer_ids)
        self.uploads = dict((pid, []) for pid in peer_ids)

    def update(self, dls, ups):
        """
        dls: dict : peer_id -> [downloads] -- downloads for this round
        ups: dict : peer_id -> [uploads] -- uploads for this round

        append these downloads to to the history
        """
        for pid in self.peer_ids:
            self.downloads[pid].append(dls[pid])
            self.uploads[pid].append(ups[pid])

    def peer_is_done(self, round, peer_id):
        # Only save the _first_ round where we hear this
        if peer_id not in self.round_done:
            self.round_done[peer_id] = round

    def peer_history(self, peer_id):
        return AgentHistory(peer_id, self.downloads[peer_id], self.uploads[peer_id])

    def last_round(self):
        """index of the last completed round"""
        p = self.peer_ids[0]
        return len(self.downloads[p])-1

    def pretty_for_round(self, r):
        s = "\nRound %s:\n" % r
        for peer_id in self.peer_ids:
            ds = self.downloads[peer_id][r]
            stringify = lambda d: "%s downloaded %d blocks of piece %d from %s\n" % (
                peer_id, d.blocks, d.piece, d.from_id)
            s += "".join(map(stringify, ds))
        return s

    def pretty(self):
        s = "History\n"
        for r in range(self.last_round()+1):
            s += self.pretty_for_round(r)
        return s

    def __repr__(self):
        return """History(
uploads=%s
downloads=%s
)""" % (
    pprint.pformat(self.uploads),
    pprint.pformat(self.downloads))

