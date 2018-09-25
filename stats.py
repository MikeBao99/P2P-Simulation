#!/usr/bin/python

class Stats:
    @staticmethod
    def uploaded_blocks(peer_ids, history):
        """
        peer_ids: list of peer_ids
        history: a History object

        Returns:
        dict: peer_id -> total upload blocks used
        """
        uploaded = dict((peer_id, 0) for peer_id in peer_ids)
        for peer_id in peer_ids:
            for ds in history.downloads[peer_id]:
                for download in ds:
                    uploaded[download.from_id] += download.blocks
                
        return uploaded

    @staticmethod
    def uploaded_blocks_str(peer_ids, history):
        """ Return a pretty stringified version of uploaded_blocks """
        d = Stats.uploaded_blocks(peer_ids, history)

        k = lambda id: d[id]
        return "\n".join("%s: %d, bw=%d" % (id, d[id], history.upload_rates[id])
                         for id in sorted(d.keys(), key=d.__getitem__))

    @staticmethod
    def completion_rounds(peer_ids, history):
        """Returns dict: peer_id -> round when completed,
        or None if not completed"""
        d = dict(history.round_done)
        for id in peer_ids:
            if id not in d:
                d[id] = None
        
        return d

    @staticmethod
    def completion_rounds_str(peer_ids, history):
        """ Return a pretty stringified version of completion_rounds """
        d = Stats.completion_rounds(peer_ids, history)

        k = lambda id: d[id]
        return "\n".join("%s: %s" % (id, d[id])
                         for id in sorted(d.keys(), key=d.__getitem__))

    @staticmethod
    def all_done_round(peer_ids, history):
        d = Stats.completion_rounds(peer_ids, history)
        if None in d.values():
            return None
        return max(d.values())
    
