#!/usr/bin/python

class Upload:
    def __init__(self, from_id, to_id, up_bw):
        self.from_id = from_id
        self.to_id = to_id
        self.bw = up_bw

    def __repr__(self):
        return "Upload(from_id = %s, to_id=%s, bw=%d)" % (
            self.from_id, self.to_id, self.bw)

class Request:
    def __init__(self, requester_id, peer_id, piece_id, start):
        self.requester_id = requester_id
        self.peer_id = peer_id   # peer data is requested from
        self.piece_id = piece_id
        self.start = start  # the block index

    def __repr__(self):
        return "Request(requester_id=%s, peer_id=%s, piece_id=%d, start=%d)" % (
            self.requester_id, self.peer_id, self.piece_id, self.start)

class Download:
    """ Not actually a message--just used for accounting and history tracking of
     what is actually downloaded.
    """
    def __init__(self, from_id, to_id, piece, blocks):
        self.from_id = from_id  # who did the agent download from?
        self.to_id = to_id      # Who downloaded?
        self.piece = piece      # Which piece?
        self.blocks = blocks    # How much did the agent download?

    def __repr__(self):
        return "Download(from_id=%s, to_id=%s, piece=%d, blocks=%d)" % (
            self.from_id, self.to_id, self.piece, self.blocks)



            
class PeerInfo:
    """
    Only passing peer ids and the pieces they have available to each agent.
    This prevents them from accidentally messing up the state of other agents.
    """
    def __init__(self, id, available):
        self.id = id
        self.available_pieces = available

    def __repr__(self):
        return "PeerInfo(id=%s)" % self.id

