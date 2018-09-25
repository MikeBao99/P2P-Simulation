#!/usr/bin/env python

"""
Simulates one file being shared amongst a set of peers.  The file is divided into a set of pieces, each comprised of some number of blocks.  There are two types of peers:
  - seeds, which start with all the pieces.  
  - regular peers, which start with no pieces.

The simulation proceeds in rounds.  In each round, peers can request pieces from other peers, and then decide how much to upload to others.  Once every peer has every piece, the simulation ends.
"""

import re
import random
import sys
import logging
import copy
import itertools
import pprint
from optparse import OptionParser

from messages import Upload, Request, Download, PeerInfo
from util import *
from stats import Stats
from history import History
    

class Sim:
    def __init__(self, config):
        self.config = config
        self.up_bws_state = dict()

    
    def up_bw(self, peer_id, reinit=False):
        """Return a consistent bw for this peer"""
        c = self.config
        s = self.up_bws_state

        # Re-initialize up-bws if we are starting a new simulation
        if reinit and peer_id in s:
            del s[peer_id]
        
        """Sets the upload bandwidth of seeds to max, other agents at random"""
        if re.match("Seed",peer_id): the_up_bw = c.max_up_bw
        else: the_up_bw = random.randint(c.min_up_bw, c.max_up_bw)
        
        return s.setdefault(peer_id, the_up_bw)

    def run_sim_once(self):
        """Return a history"""
        conf = self.config
        # Keep track of the current round.  Needs to be in scope for helpers.
        round = 0  

        def check_pred(pred, msg, Exc, lst):
            """Check if any element of lst matches the predicate.  If it does,
            raise an exception of type Exc, including the msg and the offending
            element."""
            m = map(pred, lst)
            if True in m:
                i = m.index(True)
                raise Exc(msg + " Bad element: %s" % lst[i])

        def check_uploads(peer, uploads):
            """Raise an IllegalUpload exception if there is a problem."""
            def check(pred, msg):
                check_pred(pred, msg, IllegalUpload, uploads)

            not_upload = lambda o: not isinstance(o, Upload)
            check(not_upload, "List of Uploads contains non-Upload object.")

            self_upload = lambda upload: upload.to_id == peer.id
            check(self_upload, "Can't upload to yourself.")
            
            not_from_self = lambda upload: upload.from_id != peer.id
            check(not_from_self, "Upload.from != peer id.")

            check(lambda u: u.bw < 0, "Upload bandwidth must be non-negative!")

            limit = self.up_bw(peer.id)
            if sum(map(lambda u: u.bw, uploads)) > limit:
                raise IllegalUpload("Can't upload more than limit of %d. %s" % (
                    limit, uploads))

            # If we got here, looks ok.

        def check_requests(peer, requests, peer_pieces, available):
            """Raise an IllegalRequest exception if there is a problem."""

            def check(pred, msg):
                check_pred(pred, msg, IllegalRequest, requests)

            check(lambda o: not isinstance(o, Request),
                  "List of Requests contains non-Request object.")

            bad_piece_id = lambda r: (r.piece_id < 0 or
                                      r.piece_id >= self.config.num_pieces)
            check(bad_piece_id, "Request asks for non-existent piece!")
            
            bad_peer_id = lambda r: r.peer_id not in self.peer_ids
            check(bad_peer_id, "Request mentions non-existent peer!")

            bad_requester_id = lambda r: r.requester_id != peer.id
            check(bad_requester_id, "Request has wrong peer id!")

            bad_start_block = lambda r: (
                r.start < 0 or
                r.start >= self.config.blocks_per_piece or
                r.start > peer_pieces[peer.id][r.piece_id])
            # Must request the _next_ necessary block
            check(bad_start_block, "Request has bad start block!")

            def piece_peer_does_not_have(r):
                other_peer = self.peers_by_id[r.peer_id]
                return r.piece_id not in available[other_peer.id]
            check(piece_peer_does_not_have, "Asking for piece peer does not have!")
            
            # If we got here, looks ok

        def available_pieces(peer_id, peer_pieces):
            """
            Return a list of piece ids that this peer has available.
            """
            return filter(lambda i: peer_pieces[peer_id][i] == conf.blocks_per_piece,
                          range(conf.num_pieces))

        def peer_done(peer_pieces, peer_id):
            # TODO: remove linear pass
            for blocks_so_far in peer_pieces[peer_id]:
                if blocks_so_far < conf.blocks_per_piece:
                    return False
            return True
            
        def all_done(peer_pieces):
            result = True
            # Check all peers to update done status
            for peer_id in peer_pieces:
                if peer_done(peer_pieces, peer_id):
                    history.peer_is_done(round, peer_id)
                else:
                    result = False
            return result

        def create_peers():
            """Each agent class must be already loaded, and have a
            constructor that takes the config, id,  pieces, and
            up and down bandwidth, in that order."""

            def load(class_name, params):
                agent_class = conf.agent_classes[class_name]
                return agent_class(*params)

            counts = dict()
            def index(name):
                if name in counts:
                    a = counts[name]
                    counts[name] += 1
                else:
                    a = 0
                    counts[name] = 1
                return a

            n = len(conf.agent_class_names)
            ids = map(lambda n: "%s%d" % (n,index(n)), conf.agent_class_names)

            is_seed = lambda id: id.startswith("Seed")

            def get_pieces(id):
                if id.startswith("Seed"):
                    return [conf.blocks_per_piece]*conf.num_pieces
                else:
                    return [0]*conf.num_pieces
                
            peer_pieces = dict()  # id -> list (blocks / piece)
            peer_pieces = dict((id, get_pieces(id)) for id in ids)
            pieces = [get_pieces(id) for id in ids]
            r = itertools.repeat
            
            # Re-initialize upload bandwidths at the beginning of each
            # new simulation
            up_bws = [self.up_bw(id, reinit=True) for id in ids] 
            params = zip(r(conf), ids, pieces, up_bws)

            peers = map(load, conf.agent_class_names, params)
            #logging.debug("Peers: \n" + "\n".join(str(p) for p in peers))
            return peers, peer_pieces

        def get_peer_requests(p, peer_info, peer_history, peer_pieces, available):
            def remove_me(info):
                # TODO: Do we need this linear pass?
                return filter(lambda peer: peer.id != p.id, peer_info)

            pieces = copy.copy(peer_pieces[p.id])
            # Made copy of pieces and the peer info this peer needs to make it's
            # decision, so that it can't change the simulation's copies.
            p.update_pieces(pieces)
            rs = p.requests(remove_me(peer_info), peer_history)
            check_requests(p, rs, peer_pieces, available)
            return rs

        def get_peer_uploads(all_requests, p, peer_info, peer_history):
            def remove_me(info):
                # TODO: remove this pass?  Use a set?
                return filter(lambda peer: peer.id != p.id, peer_info)

            def requests_to(id):
                f = lambda r: r.peer_id == id
                ans = []
                for rs in all_requests.values():
                    ans.extend(filter(f, rs))
                return ans

            requests = requests_to(p.id)

            us = p.uploads(requests, remove_me(peer_info), peer_history)
            check_uploads(p, us)
            return us

        def upload_rate(uploads, uploader_id, requester_id):
            """
            return the uploading rate from uploader to requester
            in blocks per time period, or 0 if not uploading.
            """
            for u in uploads[uploader_id]:
                if u.to_id == requester_id:
                    return u.bw
            return 0

        def update_peer_pieces(peer_pieces, requests, uploads, available):
            """
            Process the uploads: figure out how many blocks of all the requested
            pieces the requesters ended up with.
            Make sure requesting the same thing from lots of peers doesn't
            stack.
            update the sets of available pieces as needed.
            """
            downloads = dict()  # peer_id -> [downloads]
            new_pp = copy.deepcopy(peer_pieces)
            for requester_id in requests:
                downloads[requester_id] = list()
            for requester_id in requests:
                # Keep track of how many blocks of each piece this
                # requester got.  piece -> (blocks, from_who)
                new_blocks_per_piece = dict()
                def update_count(piece_id, blocks, peer_id):
                    if piece_id in new_blocks_per_piece:
                        old = new_blocks_per_piece[piece_id][0]
                        if blocks > old:
                            new_blocks_per_piece[piece_id] = (blocks, peer_id)
                    else:
                        new_blocks_per_piece[piece_id] = (blocks, peer_id)

                # Group the requests by peer that is being asked
                get_peer_id = lambda r: r.peer_id
                rs = sorted(requests[requester_id], key=get_peer_id)
                for peer_id, rs_for_peer in itertools.groupby(rs, get_peer_id):
                    bw = upload_rate(uploads, peer_id, requester_id)
                    if bw == 0:
                        continue
                    # This bandwidth gets applied in order to each piece requested
                    for r in rs_for_peer:
                        needed_blocks = conf.blocks_per_piece - r.start
                        alloced_bw = min(bw, needed_blocks)
                        update_count(r.piece_id, alloced_bw, peer_id)
                        bw -= alloced_bw
                        if bw == 0:
                            break
                for piece_id in new_blocks_per_piece:
                    (blocks, peer_id) = new_blocks_per_piece[piece_id]
                    new_pp[requester_id][piece_id] += blocks
                    if new_pp[requester_id][piece_id] == conf.blocks_per_piece:
                        available[requester_id].add(piece_id)
                    d = Download(peer_id, requester_id, piece_id, blocks)
                    downloads[requester_id].append(d)
                
            return (new_pp, downloads)

        def completed_pieces(peer_id, available):
            return len(available[peer_id])
        
        def log_peer_info(peer_pieces, available):
            for p_id in self.peer_ids:
                pieces = peer_pieces[p_id]
                logging.debug("pieces for %s: %s" % (str(p_id), str(pieces)))
            log = ", ".join("%s:%s" % (p_id, completed_pieces(p_id, available))
                            for p_id in self.peer_ids)
            logging.info("Pieces completed: " + log)


        logging.debug("Starting simulation with config: %s" % str(conf))

        peers, peer_pieces = create_peers()
        self.peer_ids = [p.id for p in peers]
        self.peers_by_id = dict((p.id, p) for p in peers)
        
        upload_rates = dict((id, self.up_bw(id)) for id in self.peer_ids)
        history = History(self.peer_ids, upload_rates)

        # dict : pid -> set(finished / available pieces)
        available = dict((pid, set(available_pieces(pid, peer_pieces)))
                         for pid in self.peer_ids)

        # Begin the event loop
        while True:
            logging.info("======= Round %d ========" % round)

            peer_info = [PeerInfo(p.id, available[p.id])
                         for p in peers]
            requests = dict()  # peer_id -> list of Requests
            uploads = dict()   # peer_id -> list of Uploads
            h = dict()
            for p in peers:
                h[p.id] = history.peer_history(p.id)
                requests[p.id] = get_peer_requests(p, peer_info, h[p.id], peer_pieces,
                                                   available)

            for p in peers:
                uploads[p.id] = get_peer_uploads(requests, p, peer_info, h[p.id])
                

            (peer_pieces, downloads) = update_peer_pieces(
                peer_pieces, requests, uploads, available)
            history.update(downloads, uploads)

            logging.debug(history.pretty_for_round(round))

            log_peer_info(peer_pieces, available)
           
            if all_done(peer_pieces):
                logging.info("All done!")                    
                break
            round += 1
            if round > conf.max_round:
                logging.info("Out of time.  Stopping.")
                break

        logging.info("Game history:\n%s" % history.pretty())

        logging.info("======== STATS ========")
        logging.info("Uploaded blocks:\n%s" %
                     Stats.uploaded_blocks_str(self.peer_ids, history))
        logging.info("Completion rounds:\n%s" %
                     Stats.completion_rounds_str(self.peer_ids, history))
        logging.info("All done round: %s" %
                     Stats.all_done_round(self.peer_ids, history))

        return history

    def run_sim(self):
        histories = map(lambda i: self.run_sim_once(), 
                        range(self.config.iters))
        logging.warning("======== SUMMARY STATS ========")
        
        uploaded_blocks = map(
            lambda h: Stats.uploaded_blocks(self.peer_ids, h),
            histories)
        completion_rounds = map(
            lambda h: Stats.completion_rounds(self.peer_ids, h),
            histories)

        def extract_by_peer_id(lst, peer_id):
            """Given a list of dicts, pull out the entry
            for peer_id from each dict.  Return a list"""
            return map(lambda d: d[peer_id], lst)

        uploaded_by_id = dict(
            (p_id, extract_by_peer_id(uploaded_blocks, p_id))
            for p_id in self.peer_ids)

        completion_by_id = dict(
            (p_id, extract_by_peer_id(completion_rounds, p_id))
            for p_id in self.peer_ids)

        logging.warning("Uploaded blocks: avg (stddev)")
        for p_id in sorted(self.peer_ids,
                           key=lambda id: mean(uploaded_by_id[id])):
            us = uploaded_by_id[p_id]
            logging.warning("%s: %.1f  (%.1f)" % (p_id, mean(us), stddev(us)))

        logging.warning("Completion rounds: avg (stddev)")

        def optionize(f):
            def g(lst):
                if None in lst:
                    return None
                else:
                    return f(lst)
            return g

        opt_mean = optionize(mean)
        opt_stddev = optionize(stddev)
        
        for p_id in sorted(self.peer_ids,
                           key=lambda id: opt_mean(completion_by_id[id])):
            cs = completion_by_id[p_id]
            logging.warning("%s: %s  (%s)" % (p_id, opt_mean(cs), opt_stddev(cs)))



def configure_logging(loglevel):
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)

    root_logger = logging.getLogger('')
    strm_out = logging.StreamHandler(sys.__stdout__)
#    strm_out.setFormatter(logging.Formatter('%(levelno)s: %(message)s'))
    strm_out.setFormatter(logging.Formatter('%(message)s'))
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(strm_out)
    

def parse_agents(args):
    """
    Each element is a class name like "Peer", with an optional
    count appended after a comma.  So either "Peer", or "Peer,3".
    Returns an array with a list of class names, each repeated the
    specified number of times.
    """
    ans = []
    for c in args:
        s = c.split(',')
        if len(s) == 1:
            ans.extend(s)
        elif len(s) == 2:
            name, count = s
            ans.extend([name]*int(count))
        else:
            raise ValueError("Bad argument: %s\n" % c)
    return ans
            
        

def main(args):
    usage_msg = "Usage:  %prog [options] PeerClass1[,count] PeerClass2[,count] ..."
    parser = OptionParser(usage=usage_msg)

    def usage(msg):
        print "Error: %s\n" % msg
        parser.print_help()
        sys.exit()
    
    parser.add_option("--loglevel",
                      dest="loglevel", default="info",
                      help="Set the logging level: 'debug' or 'info'")

    parser.add_option("--num-pieces",
                      dest="num_pieces", default=3, type="int",
                      help="Set number of pieces in the file")

    parser.add_option("--blocks-per-piece",
                      dest="blocks_per_piece", default=4, type="int",
                      help="Set number of blocks per piece")

    parser.add_option("--max-round",
                      dest="max_round", default=5, type="int",
                      help="Limit on number of rounds")

    parser.add_option("--min-bw",
                      dest="min_up_bw", default=4, type="int",
                      help="Min upload bandwidth")

    parser.add_option("--max-bw",
                      dest="max_up_bw", default=10, type="int",
                      help="Max upload bandwidth")

    parser.add_option("--iters",
                      dest="iters", default=1, type="int",
                      help="Number of times to run simulation to get stats")


    (options, args) = parser.parse_args()

    # leftover args are class names, with optional counts:
    # "Peer Seed[,4]"

    if len(args) == 0:
        # default
        agents_to_run = ['Dummy', 'Dummy', 'Seed']
    else:
        try:
            agents_to_run = parse_agents(args)
        except ValueError, e:
            usage(e)
    
    configure_logging(options.loglevel)
    config = Params()

    config.add("agent_class_names", agents_to_run)
    config.add("agent_classes", load_modules(config.agent_class_names))

    
    config.add("num_pieces", options.num_pieces)
    config.add("blocks_per_piece",options.blocks_per_piece)
    config.add("max_round", options.max_round)
    config.add("min_up_bw", options.min_up_bw)
    config.add("max_up_bw", options.max_up_bw)
    config.add("iters", options.iters)
    
    sim = Sim(config)
    sim.run_sim()

if __name__ == "__main__":

    # The next two lines are for profiling...
    import cProfile
    cProfile.run('main(sys.argv)', 'out.prof')
#    main(sys.argv)
