from midca.worldsim import domainread, stateread
from midca import rosrun, midcatime, base
import copy
import os
import socket

try:
	# baxter robot requirements
	from midca.examples import ObjectDetector
	from bzrlib.config import LocationStore
except:
	pass

class ROSObserver:

    def init(self, world, mem):
        self.mem = mem
        self.mem.set(self.mem.STATE, world_repr.SimpleWorld())

    def store_history(self,world,history,blocks):
	'''
	store the history of last 5 state changes
	'''
	if blocks:
		a = {}
		for each in blocks:
			positions= world.all_pos(each)
			a[each] = positions.pop().position

		if a:
			history = history.append(a)

		if not history:
			history = []

		if len(history) > 5:
			history = history[:5]

		history.reverse()
		return history
	return None




    def check_with_history(self,world,history,detectionEvents):
	'''
	store the past 5 change in events for the robot to remember things
	'''
	blocks = set()
	for each in detectionEvents:
		blocks.add(each.id)
	if not history:
		history = []
		self.store_history(world,history,blocks)
	else:
		if not len(blocks) == len(history[len(history) -1]):
			history = self.store_history(world,history,blocks)
	return history

    def run(self, cycle, verbose = 2):
        #self.ObserveWorld()
        detectionEvents = self.mem.get_and_clear(self.mem.ROS_OBJS_DETECTED)
        detecttionBlockState = self.mem.get_and_clear(self.mem.ROS_OBJS_STATE)
        utteranceEvents = self.mem.get_and_clear(self.mem.ROS_WORDS_HEARD)
        feedback = self.mem.get_and_clear(self.mem.ROS_FEEDBACK)
        world = self.mem.get_and_lock(self.mem.STATE)
        history = self.mem.get_and_lock(self.mem.STATE_HISTORY)

        if not detectionEvents:
            detectionEvents = []
        if not detecttionBlockState:
            detecttionBlockState = []
        if not utteranceEvents:
            utteranceEvents = []
        if not feedback:
            feedback = []
        for event in detectionEvents:
            event.time = midcatime.now()
            world.sighting(event)
        for blockstate in detecttionBlockState:
            blockstate.time = midcatime.now()
            world.position(blockstate)
        for event in utteranceEvents:
            event.time = midcatime.now()
            world.utterance(event)
        for msg in feedback:
            d = rosrun.msg_as_dict(msg)
            d['received_at'] = float(midcatime.now())
            self.mem.add(self.mem.FEEDBACK, d)

	# if there are any change in events remember
	history = self.check_with_history(world,history,detecttionBlockState)
	self.mem.unlock(self.mem.STATE_HISTORY)
	if history:
		if len(history) > 5:
			history = history[:5]
		self.mem.set(self.mem.STATE_HISTORY , history)
        self.mem.unlock(self.mem.STATE)


        if verbose > 1:
            print "World observed:", len(detectionEvents), "new detection event(s),", len(utteranceEvents), "utterance(s) and", len(feedback), "feedback msg(s)"



class PerfectObserver(base.BaseModule):

    '''
    MIDCA Module which copies a complete world state. It is designed to interact with the
    built-in MIDCA world simulator. To extend this to work with other representations,
    modify the observe method so that it returns an object representing the current known
    world state.
    '''

    def init(self, world, mem):
        base.BaseModule.init(self, mem)
        if not world:
            raise ValueError("world is None!")
        self.world = world

    #perfect observation
    def observe(self):
        return self.world.copy()

    def run(self, cycle, verbose = 2):
        world = self.observe()
        if not world:
            raise Exception("World observation failed.")
        self.mem.add(self.mem.STATES, world)

        # Memory Usage Optimization (optional, feel free to comment
        # drop old memory states if not being used
        # this should help with high memory costs
        states = self.mem.get(self.mem.STATES)
        if len(states) > 400:
            #print "trimmed off 200 old stale states"
            states = states[200:]
            self.mem.set(self.mem.STATES, states)
        # End Memory Usage Optimization

        if verbose >= 1:
            print "World observed."

        trace = self.mem.trace
        if trace:
            trace.add_module(cycle, self.__class__.__name__)
            trace.add_data("WORLD",copy.deepcopy(world))


class MoosObserver(base.BaseModule):
    '''
    MIDCA Module which interacts with moos to get the current states
    of the vehicle in the moos.
    '''

    def init(self, world, mem):
        base.BaseModule.init(self, mem)
        if not world:
            raise ValueError("world is None!")
        self.world = world
        context = zmq.Context()
        self.subscriber = context.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, '')
        self.subscriber.setsockopt(zmq.RCVTIMEO, 1)
        self.subscriber.setsockopt(zmq.CONFLATE, 1)
        self.subscriber.connect("tcp://127.0.0.1:5563")


    # perfect observation
    def observe(self):
        return self.world.copy()

    def run(self, cycle, verbose=2):
        '''
        Read from the subscriber in the format "X:float,Y:float,SPEED:float"
        '''
        world = self.observe()
        if not world:
            raise Exception("World observation failed.")
        self.mem.add(self.mem.STATES, world)

        x = -1
        y = -1
        speed = -1
        states = ""

        '''
        The following code gets the current X,Y,Speed and updates the location of uuv.
        i.e., if the vehicle is in qroute or green area 1 or green area 2.
        the else part is to remove the state after the vehicle leaves the specific location
        '''

        try:
            current_position = self.subscriber.recv()
            x,y,speed = current_position.split(",")
            x = float(x.split(":")[1])
            y = float(y.split(":")[1])
            speed = float(speed.split(":")[1])

            if y >=-98 and y<=-48:
                states+="at_location(remus,qroute)\n"
            else:
                for atom in self.world.atoms:
                    if atom.predicate.name == "at_location" \
                            and atom.args[0].name == "remus"\
                            and atom.args[1].name == "qroute":
                        self.world.atoms.remove(atom)
                        break

            if x>=-2 and x<=40 and y>=-96 and y<=-63:
                states+="at_location(remus,ga1)"
            else:
                for atom in self.world.atoms:
                    if atom.predicate.name == "at_location" \
                            and atom.args[0].name == "remus"\
                            and atom.args[1].name == "ga1":
                        self.world.atoms.remove(atom)
                        break

            if x>=120 and x<=175 and y>=-96 and y<=-63:
                states+="at_location(remus,ga2)"
            else:
                for atom in self.world.atoms:
                    if atom.predicate.name == "at_location" \
                            and atom.args[0].name == "remus"\
                            and atom.args[1].name == "ga2":
                        self.world.atoms.remove(atom)
                        break
        except:
            pass
        # this is to update the world into memory
        if not states == "":
            if verbose >= 1:
                print(states)
            stateread.apply_state_str(self.world, states)
            self.mem.add(self.mem.STATES, self.world)


        states = self.mem.get(self.mem.STATES)
        if len(states) > 400:
            # print "trimmed off 200 old stale states"
            states = states[200:]
            self.mem.set(self.mem.STATES, states)
        # End Memory Usage Optimization

        if verbose >= 1:
            print "World observed."

        trace = self.mem.trace
        if trace:
            trace.add_module(cycle, self.__class__.__name__)
            trace.add_data("WORLD", copy.deepcopy(self.world))



class PerfectObserverWithThief(base.BaseModule):

    '''
    MIDCA Module which copies a complete world state. It is designed to interact with the
    built-in MIDCA world simulator. To extend this to work with other representations,
    modify the observe method so that it returns an object representing the current known
    world state.
    '''

    def init(self, world, mem):
        base.BaseModule.init(self, mem)
        if not world:
            raise ValueError("world is None!")
        self.world = world

    #perfect observation
    def observe(self):
        return self.world.copy()

    def run(self, cycle, verbose = 2):
        world = self.observe()
        thisDir = os.path.dirname(os.path.realpath(__file__))
        thief_file = thisDir + "/theif.txt"
        theft_items=[]
		
        with open(thief_file) as f:
	    	lines = f.readlines()
	    	for line in lines:
	    		theft_items.append(line.split(" "))


        if not world:
            raise Exception("World observation failed.")

#         self.mem.add(self.mem.STATES, world)

        for item in theft_items:

			for atom in world.atoms:
				if atom.predicate.name == item[0] and atom.args[0].name == item[1]:
					world.atoms.remove(atom)
					print("removed:" + atom.args[0].name)
					break

        self.mem.add(self.mem.STATES, world)

        # Memory Usage Optimization (optional, feel free to comment
        # drop old memory states if not being used
        # this should help with high memory costs
        states = self.mem.get(self.mem.STATES)
        if len(states) > 400:
            #print "trimmed off 200 old stale states"
            states = states[200:]
            self.mem.set(self.mem.STATES, states)
        # End Memory Usage Optimization

        if verbose >= 1:
            print "World observed."

        trace = self.mem.trace
        if trace:
            trace.add_module(cycle, self.__class__.__name__)
            trace.add_data("WORLD",copy.deepcopy(world))



class MAReport:

    namecounts = {"report": 0}

    def __init__(self):
        self.actions = []
        self.finalstate = None

    def str_dict(self, item, numtabs = 1, skipfirsttab = True):
        if isinstance(item, dict):
            s = ""
            first = True
            for key in sorted(item.keys()):
                if not first or not skipfirsttab:
                    s += "\t" * numtabs
                else:
                    s += " "
                s += "(" + str(key) + " " + self.str_dict(item[key], numtabs + 1) + ")\n"
                first = False
            s = s[:-1]
        else:
            s = str(item)
        return s

    def action_str(self, action):
        if action[0] in self.namecounts:
            self.namecounts[action[0]] += 1
        else:
            self.namecounts[action[0]] = 1
        s = "(" + str(action[0]) + "." + str(self.namecounts[action[0]]) + "\n"
        valuepairs = {}
        if action[0] in ("stack", "unstack", "pickup", "putdown", "apprehend", "putoutfire"):
            valuepairs["actor"] = {"value": "person.0"}
        elif action[0] == "burns":
            valuepairs["actor"] = {"value": "nature"}
        valuepairs["object"] = {"value": str(action[1]).replace(" ", "_")}
        if action[0] in ("stack", "unstack"):
            valuepairs["recipient"] = {"value": str(action[2]).replace(" ", "_")}
        return s + self.str_dict(valuepairs, skipfirsttab = False) + ")"

    def atom_pairs(self, atom):
        valuepairs = {}
        for i in range(len(atom.args)):
            if i == 0:
                valuepairs["domain"] = {"value": atom.args[i].name.replace(" ", "_")}
            elif i == 1:
                valuepairs["co-domain"] = {"value": atom.args[i].name.replace(" ", "_")}
        return valuepairs

    def state_str(self, world):
        s = "(state\n"
        valuepairs = {}
        for atom in world.atoms:
            if atom.predicate.name in self.namecounts:
                self.namecounts[atom.predicate.name] += 1
            else:
                self.namecounts[atom.predicate.name] = 1
            valuepairs[atom.predicate.name + "." + str(self.namecounts[atom.predicate.name])] = self.atom_pairs(atom)
        return s + self.str_dict(valuepairs, skipfirsttab = False) + ")"


    def __str__(self):
        #if not self.actions:
        #    return "incomplete"
        # if there is no state do not send report to meta aqua
        if not self.finalstate:
            return "incomplete"
        else:
            self.namecounts["report"] += 1
            s = "(" + "report." + str(self.namecounts["report"]) + "\n("
            for action in self.actions:
                s += "\t(\n"
                s += self.action_str(action)
                s += "\n\"\")\n("
                s += self.state_str(self.finalstate)
                s += "\n\"\")\n"
            return s + "))"

'''
ma = MAReport()
import domainread, stateread
world = domainread.load_domain("./domain.sim")
stateread.apply_state_file(world, "./defstate.sim")
ma.finalstate = world
ma.actions.append(["unstack", "block1", "block2"])
ma.actions.append(["catchfire", "block1"])
print ma
'''

class MAReporter(base.BaseModule):

    '''
    MIDCA module that sends a report on the world and actions to the
    Meta-AQUA story understanding system. This requires Meta-AQUA to be
    running or it will not work. Also depends on the basic observation
    module.
    '''

    def __init__(self, writePort):
        self.writeS = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.writeS.connect(("localhost", writePort))

    def get_lit_blocks(self, world):
        res = []
        for objectname in world.objects:
            if world.is_true("onfire", [objectname]) and \
            world.objects[objectname].type.name == "BLOCK" and \
            objectname != "table":
                res.append(objectname)
        return res


    def run(self, cycle, verbose = 2):
        world = None
        lastWorld = None
        try:
            world = self.mem.get(self.mem.STATES)[-1]
            lastWorld = self.mem.get(self.mem.STATES)[-2]
        except (TypeError,IndexError):
            pass
        if not world:
            return #no report if not world observed
        report = MAReport()
        report.finalstate = world
        try:
            actions = self.mem.get(self.mem.ACTIONS)[-1]
        except (TypeError, IndexError):
            actions = []
        blocksPutOut = []
        for action in actions:
            action.args = list(action.args)
            report.actions.append([action.op] + action.args)
            if action.op == "putoutfire":
                blocksPutOut.append(action.args[0])
        if lastWorld:
            lastBurning = self.get_lit_blocks(lastWorld)
            burning = self.get_lit_blocks(world)
            for block in burning:
                if block not in lastBurning or block in blocksPutOut:
                    report.actions.append(["burns", block])
        #report is finished, send to Meta-AQUA
		#report contains actions and state,
		#for every action there will be the state attached to it
        if verbose >= 1:
            print "Sending report to Meta-AQUA",
            if verbose >= 2:
                print ":\n", report
        if not str(report ) == "incomplete":
            self.writeS.send(str(report))

    def __del__(self):
        '''
            close sockets on deletion. Also send 'Done' message to Meta-AQUA.
        '''
        try:
            self.writeS.send(self.endMsg)
        finally:
            self.writeS.shutdown(socket.SHUT_RDWR)


class GraceMidcaPercieve():
    '''
    class that provides high level perception of Grace data for midca example
    '''

    def init(self):  # initiallizes socket connection library to communicate with and control grace
        import sys
        gracePath = '/home/pi/Desktop/Grace_Control'

        sys.path.insert(0, gracePath)
        import GliderFunIPC
        self.interface = GliderFunIPC.graceFun()
        self.bottomDepth = -1
        self.gracePath = gracePath


    def senseDepth(self):  # reads the pressure sensor and converts it to depth in meters
        grace = self.interface
        return grace.readDepth()


    def beginBottomCheck(self):  # will call the function to check at bottom
        import os
        os.system("./findBottom")


    def checkAtBottom(self):  # read a file output by program chechinkg for bottom and return true or false
        atBottom = False
        gracePath = ""
        f = open(gracePath + "atBottom", 'r')
        atBottom = (1 == int(f.readline()))
        f.close()
        if atBottom:
            f = open(gracePath + "atBottom", 'w')
            f.write("0")
            f.close()
            grace = self.interface
        self.bottomDepth = grace.readDepth()
        return atBottom


    def checkCommunicationAck(self):  # read a file output by program chechinkg for surface and return true or false
        # sending $%GO%$ over xbee will cause a file "Next_Dive_GO" to be produce with 1 in line one
        Acknowleged = False
        gracePath = ""
        f = open(gracePath + "Next_Dive_GO", 'r')
        Acknowleged = (1 == int(f.readline()))
        f.close()

        # to remove error
        f = open(gracePath + "atBottom", 'r')
        atBottom = (1 == int(f.readline()))
        f.close()
        #
        if atBottom:
            f = open(gracePath + "Next_Dive_GO", 'w')
            f.write("0")
            f.close()
        return Acknowleged


    def checkAtSurfaceDepth(self):  # chechs if depth is close enough to say we are surfaced
        grace = self.interface
        depth = grace.readDepth()
        return depth <= .2


class GraceObserver(base.BaseModule):
    '''
    MIDCA Module communicates with the grace to obtain the world states
    '''

    def init(self, world, mem):
        """
        This function is only called during the initialization of midca
        So, it is a one time function call
        """

        base.BaseModule.init(self, mem)
        if not world:
            raise ValueError("world is None!")
        self.world = world
        self.GracePerception = GraceMidcaPercieve()  # initallizes Grace Midca Percive class for easy access to high level signals midca needs
        self.runningBottomCheck = False  # flag to see if we are already checking for bottom
        # can initialize here ..


    # perfect observation
    def observe(self):
        return self.world.copy()


    def run(self, cycle, verbose=2):
        '''
        Read from the subscriber in the format "X:float,Y:float,SPEED:float"
        '''
        world = self.observe()
        if not world:
            raise Exception("World observation failed.")
        self.mem.add(self.mem.STATES, world)

        '''
        The following code gets the depth and the acknowledgement from grace
        to create states for the world.
        For example : Should comeback and complete this later
        '''
        states = ""
        try:
            # write the function to aquire depth and acknowledgement
            GP = self.GracePerception

            atSurface = GP.checkAtSurfaceDepth()  # checks if depth is close to surface depth
            if not self.runningBottomCheck and not atSurface:  # only check for bottom if we are not already doing it
                GP.beginBottomCheck()
                self.runningBottomCheck = True

            acknowledge = GP.checkCommunicationAck()  # check if we have recieved acknowledgment from fumin
            atBottom = GP.checkAtBottom()  # check if we have determined that we are at the bottom
            if atSurface or acknowledge:
                states += "at_surface(grace)\n"

                # similarly for bottom
            elif atBottom:
                states += "at_bottom(grace)\n"
                self.runningBottomCheck = False
                # for pool depth (there can be multiple pooldepths)
                # we should discuss on how many pool depths we should have

                if acknowledge:
                    states += "knows(fumin, pooldepth1)\n"





        except:
            # if there is any failure to acess the grace functions, lets
            # use this block (to be completed later)
            pass


        # this is to update the world into memory
        if not states == "":
            if verbose >= 1:
                print(states)
            stateread.apply_state_str(self.world, states)
            self.mem.add(self.mem.STATES, self.world)

        states = self.mem.get(self.mem.STATES)
        if len(states) > 400:
            # print "trimmed off 200 old stale states"
            states = states[200:]
            self.mem.set(self.mem.STATES, states)
        # End Memory Usage Optimization

        if verbose >= 1:
            print "World observed."

        trace = self.mem.trace
        if trace:
            trace.add_module(cycle, self.__class__.__name__)
            trace.add_data("WORLD", copy.deepcopy(self.world))

