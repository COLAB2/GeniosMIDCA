from _plan import pyhop
from _plan import modified_pyhop
from midca import plans, base
from midca.modules._plan.asynch import asynch_3d
from midca.modules._plan.jShop import JSHOP, JSHOP2
from midca.modules._plan.pyhop import print_state,  print_methods, print_operators
import collections
import traceback
import copy
import time
import itertools


class GenericPyhopPlanner(base.BaseModule):

    '''
    Whereas the PyHopPlanner class below is optimized for use with MIDCA's built-in world
    simulator, this planner is more generalized. It assumes that the world state stored
    in MIDCA's memory is also the world state that will be expected by the planning
    methods and operators. Also, it expects to receive 'declare_methods' and
    'declare_operators' methods as arguments. These should initialize pyhop for the
    desired planning domain. The plan_validator arg should be a method which takes a
    world state and a plan as args and returns whether the plan should be used. This will
    only be called on old plans that are retrieved.
    '''

    def __init__(self, declare_methods, declare_operators, declare_monitors=None, plan_validator = None):
        try:
            declare_methods()
            declare_operators()
            if declare_monitors:
                declare_monitors()
            self.working = True
        except:
            print "Error declaring pyhop methods and operators. This planner will be \
            disabled"
            traceback.print_exc()
            self.working = False
        self.validate_plan = plan_validator
                #note by default (no plan validator)
        #plans execute to completion unless goals change

    def get_old_plan(self, state, goals, verbose = 2):
        try:
            plan = self.mem.get(self.mem.GOAL_GRAPH).getMatchingPlan(goals)
            if not plan:
                return None
            try:
                if self.validate_plan:
                    valid = self.validate_plan(state, plan)
                    if valid:
                        if verbose >= 2:
                            print "Old plan found that tests as valid:", plan
                    else:
                        if verbose >= 2:
                            print "Old plan found that tests as invalid:", plan, ". removing from stored plans."
                        self.mem.get(self.mem.GOAL_GRAPH).removePlan(plan)
                else:
                    if verbose >= 2:
                        print "no validity check specified. assuming old plan is valid."
                        valid = True
            except:
                if verbose >= 2:
                    print "Error validating plan:", plan
                valid = False
        except:
            print "Error checking for old plans"
            plan = None
            valid = False
        if valid:
            return plan
        return None

    def get_new_plan(self, state, goals, verbose = 2):
        '''
            Calls the pyhop planner to generate a new plan.
        '''

        if verbose >= 2:
            print "Planning..."
        try:
            plan = pyhop.pyhop(state, [("achieve_goals", goals)], verbose = 0)
            #note: MIDCA does not convert its state and goals to pyhop state and
            #goal objects. Therefore, pyhop will not print correctly if verbose is
            #set to other than 0.
        except:
            if verbose >= 1:
                print "Error in planning:", traceback.format_exc(), "\n-Planning failed."
            return None
        return plan

    def get_new_modified_plan(self, state, goals, verbose = 2):
        '''
            Calls the pyhop planner to generate a new plan.
        '''

        if verbose >= 2:
            print "Planning..."
        try:
            plan = modified_pyhop.pyhop(state, [("achieve_goals", goals)], verbose = 0)
            #note: MIDCA does not convert its state and goals to pyhop state and
            #goal objects. Therefore, pyhop will not print correctly if verbose is
            #set to other than 0.
        except:
            if verbose >= 1:
                print "Error in planning:", traceback.format_exc(), "\n-Planning failed."
            return None
        return plan

    def run(self, cycle, verbose = 2):
        state = self.mem.get(self.mem.STATE)
        if not state:
            states  = self.mem.get(self.mem.STATES)
            if states:
                state = states[-1]
            else:
                if verbose >= 1:
                    print "No world state loaded. Skipping planning."
                return
        #now state is the most recent (or only) state and is non-null
       	try:
            goals = self.mem.get(self.mem.CURRENT_GOALS)[-1]
        except:
            goals = []
        if not goals:
            if verbose >= 2:
                print "No goals received by planner. Skipping planning."
            return
        plan = self.get_old_plan(state, goals, verbose)
        if verbose >= 2:
            if plan:
                print "Will not replan"
            else:
                print "Planning from scratch"
        if not plan:
            plan = self.get_new_plan(state, goals, verbose)
            if not plan and plan != []:
                return
            #convert to MIDCA plan format
            plan = plans.Plan(
                              [plans.Action(action[0], *action[1:]) for
                               action in plan], goals)
            if verbose >= 1:
                print "Planning complete."
        if verbose >= 2:
            print "Plan: ", plan
        #save new plan
        if plan != None:
            self.mem.get(self.mem.GOAL_GRAPH).addPlan(plan)


class AsynchPyhopPlanner_3d_camera(GenericPyhopPlanner):

    '''
    This planner is the same as the GenericPyhopPlanner, but it returns an asynchronous
    plan.
    '''

    def __init__(self, declare_methods, declare_operators,declare_monitors):
                GenericPyhopPlanner.__init__(self, declare_methods,declare_operators,declare_monitors,
                lambda state, plan: asynch.FAILED not in [action.status for action in plan])


    def run(self, cycle, verbose = 2):
        state = self.mem.get(self.mem.STATE)
        if not state:
            states  = self.mem.get(self.mem.STATES)
            if states:
                state = states[-1]
            else:
                if verbose >= 1:
                    print "No world state loaded. Skipping planning."
                return
        #now state is the most recent (or only) state and is non-null
        try:
            goals = self.mem.get(self.mem.CURRENT_GOALS)[-1]
        except:
            goals = []
        if not goals:
            if verbose >= 2:
                print "No goals received by planner. Skipping planning."
            return
        plan = self.get_old_plan(state, goals, verbose)
        if verbose > 2:
            if plan:
                print "Will not replan"
            else:
                print "Will replan"
        if plan:
            return
        if not plan:
            	plan = self.get_new_modified_plan(state, goals, verbose)
        if not plan:
            return
        midcaPlan = plans.Plan(plan, goals)
	asynchPlan = asynch_3d.asynch_plan(self.mem, midcaPlan)
        if verbose >= 1:
            print "Planning complete."
            if verbose >= 2:
                print "Plan: ", asynchPlan
        #save new plan
        if asynchPlan != None:
            self.mem.get(self.mem.GOAL_GRAPH).addPlan(asynchPlan)


class JSHOP2Planner(base.BaseModule):
    '''
    MIDCA module that implements a python version of the SHOP hierarchical task network (HTN) planner. HTN planners require a set of user-defined methods to generate plans; these are defined in the methods python module and declared in the constructor for this class.
    Note that this module uses has several methods to translate between MIDCA's world and goal representations and those used by pyhop; these should be changed if a new domain is introduced.
    '''

    jshop_state_from_world = None
    jshop_tasks_from_goals = None
    domain_file = ""
    state_file = ""

    def __init__(self,
                 jshop_state_from_world,
                 jshop_tasks_from_goals,
                 domain_file,
                 state_file,
                 extinguishers = False,
                 mortar = False):

        self.jshop_state_from_world = jshop_state_from_world
        self.jshop_tasks_from_goals = jshop_tasks_from_goals
        self.domain_file = domain_file
        self.state_file= state_file

        try:
            self.working = True
        except:
            print "Error declaring pyhop methods and operators. This planner will be \
            disabled"
            traceback.print_exc()
            self.working = False

    def init(self, world, mem):
        self.world = world
        self.mem = mem
        self.mem.set(self.mem.PLANNING_COUNT, 0)
    #this will require a lot more error handling, but ignoring now for debugging.
    def run(self, cycle, verbose = 2):
        world = self.mem.get(self.mem.STATES)[-1]
        try:
            goals = self.mem.get(self.mem.CURRENT_GOALS)[-1]
        except:
            goals = []

        trace = self.mem.trace
        if trace:
            trace.add_module(cycle,self.__class__.__name__)
            trace.add_data("WORLD", copy.deepcopy(world))
            trace.add_data("GOALS", copy.deepcopy(goals))

        if not goals:
            if verbose >= 2:
                print "No goals received by planner. Skipping planning."
            return
        try:
            midcaPlan = self.mem.get(self.mem.GOAL_GRAPH).getMatchingPlan(goals)
        except AttributeError:
            midcaPlan = None
        if midcaPlan:
            if verbose >= 2:
                print "Old plan retrieved. Checking validity...",
            valid = world.plan_correct(midcaPlan)
            if not valid:
                midcaPlan = None
                #if plan modification is added to MIDCA, do it here.
                if verbose >= 2:
                    print "invalid."
            elif verbose >= 2:
                print "valid."
            if valid:
                if verbose >= 2:
                    print "checking to see if all goals are achieved...",
                achieved = world.plan_goals_achieved(midcaPlan)
                if verbose >= 2:
                    if len(achieved) == len(midcaPlan.goals):
                        print "yes"
                    else:
                        print "no. Goals achieved: " + str({str(goal) for goal in achieved})
                if len(achieved) != len(midcaPlan.goals):
                    midcaPlan = None #triggers replanning.

        #ensure goals is a collection to simplify things later.
        if not isinstance(goals, collections.Iterable):
            goals = [goals]

        if not midcaPlan:
            #use pyhop to generate new plan
            if verbose >= 2:
                print "Planning..."
#             try:
            jshopState = self.jshop_state_from_world(world, self.state_file)
#             except Exception:
#                 print "Could not generate a valid pyhop state from current world state. Skipping planning"
#             try:
            jshopTasks = self.jshop_tasks_from_goals(goals,jshopState, self.state_file)
#             except Exception:
#                 print "Could not generate a valid pyhop task from current goal set. Skipping planning"
            try:
                self.mem.set(self.mem.PLANNING_COUNT, 1+self.mem.get(self.mem.PLANNING_COUNT))
                jshopPlan = JSHOP2.jshop(jshopTasks, self.domain_file, self.state_file)
            except Exception:
                jshopPlan = None
            if not jshopPlan and jshopPlan != []:
                if verbose >= 1:
                    print "Planning failed for ",
                    for goal in goals:
                        print goal, " ",
                    print
                if trace: trace.add_data("PLAN", jshopPlan)
                return
            #change from jshop plan to MIDCA plan
            midcaPlan = plans.Plan([plans.Action(action[0], *list(action[1:])) for action in jshopPlan], goals)

            if verbose >= 1:
                print "Planning complete."
            if verbose >= 2:
                print "Plan: "#, midcaPlan
                for a in midcaPlan:
                    print("  "+str(a))
            #save new plan
            if midcaPlan != None:
                self.mem.get(self.mem.GOAL_GRAPH).addPlan(midcaPlan)
            if trace: trace.add_data("PLAN",midcaPlan)


class JSHOPPlanner(base.BaseModule):
    '''
    MIDCA module that implements a python version of the SHOP hierarchical task network (HTN) planner. HTN planners require a set of user-defined methods to generate plans; these are defined in the methods python module and declared in the constructor for this class.
    Note that this module uses has several methods to translate between MIDCA's world and goal representations and those used by pyhop; these should be changed if a new domain is introduced.
    '''

    jshop_state_from_world = None
    jshop_tasks_from_goals = None
    domain_file = ""
    state_file = ""

    def __init__(self,
                 jshop_state_from_world,
                 jshop_tasks_from_goals,
                 domain_file,
                 state_file,
                 extinguishers = False,
                 mortar = False):

        self.jshop_state_from_world = jshop_state_from_world
        self.jshop_tasks_from_goals = jshop_tasks_from_goals
        self.domain_file = domain_file
        self.state_file= state_file

        self.validate_plan = lambda plan: asynch.FAILED not in [action.status for action in plan]

        try:
            self.working = True
        except:
            print "Error declaring pyhop methods and operators. This planner will be \
            disabled"
            traceback.print_exc()
            self.working = False

    def get_old_plan(self, goals, verbose = 2):
        try:
            plan = self.mem.get(self.mem.GOAL_GRAPH).getMatchingPlan(goals)
            if not plan:
                return None
            try:
                if self.validate_plan:
                    valid = self.validate_plan(plan)
                    if valid:
                        if verbose >= 2:
                            print "Old plan found that tests as valid:", plan
                    else:
                        if verbose >= 2:
                            print "Old plan found that tests as invalid:", plan, ". removing from stored plans."
                        self.mem.get(self.mem.GOAL_GRAPH).removePlan(plan)
                else:
                    if verbose >= 2:
                        print "no validity check specified. assuming old plan is valid."
                        valid = True
            except:
                if verbose >= 2:
                    print "Error validating plan:", plan
                valid = False
        except:
            print "Error checking for old plans"
            plan = None
            valid = False
        if valid:
            return plan
        return None

    def init(self, world, mem):
        self.world = world
        self.mem = mem
        self.mem.set(self.mem.PLANNING_COUNT, 0)


    #this will require a lot more error handling, but ignoring now for debugging.
    def run(self, cycle, verbose = 2):
        world = self.mem.get(self.mem.STATES)[-1]
        try:
            goals = self.mem.get(self.mem.CURRENT_GOALS)[-1]
        except:
            goals = []

        trace = self.mem.trace
        if trace:
            trace.add_module(cycle,self.__class__.__name__)
            trace.add_data("WORLD", copy.deepcopy(world))
            trace.add_data("GOALS", copy.deepcopy(goals))

        if not goals:
            if verbose >= 2:
                print "No goals received by planner. Skipping planning."
            return
        try:
            midcaPlan = self.mem.get(self.mem.GOAL_GRAPH).getMatchingPlan(goals)
        except AttributeError:
            midcaPlan = None
        if midcaPlan:
            if verbose >= 2:
                print "Old plan retrieved. Checking validity...",
            valid = world.get_old_plan(goals)
            if not valid:
                midcaPlan = None
                #if plan modification is added to MIDCA, do it here.
                if verbose >= 2:
                    print "invalid."
            elif verbose >= 2:
                print "valid."

        #ensure goals is a collection to simplify things later.
        if not isinstance(goals, collections.Iterable):
            goals = [goals]

        if not midcaPlan:
            #use jshop to generate new plan
            if verbose >= 2:
                print "Planning..."
            try:
                jshopState = self.jshop_state_from_world(world, self.state_file)
            except Exception:
                print "Could not generate a valid jshop state from current world state. Skipping planning"
            try:
                jshopTasks = self.jshop_tasks_from_goals(goals,jshopState, self.state_file)
            except Exception:
                print "Could not generate a valid jshop task from current goal set. Skipping planning"
            try:
                self.mem.set(self.mem.PLANNING_COUNT, 1+self.mem.get(self.mem.PLANNING_COUNT))
                jshopPlan = JSHOP.jshop(jshopTasks, self.domain_file, self.state_file)
            except Exception:
                jshopPlan = None
            if not jshopPlan and jshopPlan != []:
                if verbose >= 1:
                    print "Planning failed for ",
                    for goal in goals:
                        print goal, " ",
                    print
                if trace: trace.add_data("PLAN", jshopPlan)
                return
            #change from jshop plan to MIDCA plan
            midcaPlan = plans.Plan([plans.Action(action[0], *list(action[1:])) for action in jshopPlan], goals)
            asynchPlan = asynch_3d.asynch_plan(self.mem, midcaPlan)

            if verbose >= 1:
                print "Planning complete."
            if verbose >= 2:
                print "Plan: "#, midcaPlan
                for a in midcaPlan:
                    print("  "+str(a))
            #save new plan
            # save new plan
            if asynchPlan != None:
                self.mem.get(self.mem.GOAL_GRAPH).addPlan(asynchPlan)
            if trace: trace.add_data("PLAN",midcaPlan)
