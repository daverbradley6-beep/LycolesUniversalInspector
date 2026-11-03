#!/usr/bin/env python3
"""Derive composable gameplay candidates from validated client-visible evidence.

The output describes structural candidates and temporal correlations. It never
turns names, state transitions, or request text into causal or executable claims.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

SCHEMA_VERSION="110.gameplay-understanding.1"
MAX_FEATURES=5000
MAX_EVENTS=2000
MAX_CHANGES=32
MAX_TEXT=240
SCALARS=(str,int,float,bool)

FEATURE_SYSTEMS={
    "pets":("companion_collection","Companions and collectible entities"),
    "shops":("commerce","Purchasing and exchange"),
    "travel":("navigation","World traversal and area access"),
    "quests":("task_progression","Tasks and objective progression"),
    "rewards":("reward_collection","Repeatable and milestone rewards"),
    "combat":("combat","Combat and opponent interaction"),
    "inventory":("item_management","Inventory and equipment"),
    "training":("resource_progression","Repeatable stat or resource progression"),
    "progression":("resource_progression","Repeatable stat or resource progression"),
    "rebirth":("prestige_progression","Reset-based progression"),
    "bosses":("boss_encounters","Boss or arena encounters"),
    "crafting":("crafting","Item transformation and upgrades"),
}
SYSTEM_ALIASES={
    "companion_collection":{"pet","pets","egg","eggs","hatch","companion"},
    "commerce":{"shop","shops","buy","purchase","sell","upgrade","currency"},
    "navigation":{"travel","teleport","portal","world","area","move"},
    "task_progression":{"quest","quests","mission","objective","task"},
    "reward_collection":{"reward","rewards","claim","chest","gift","daily"},
    "combat":{"combat","attack","aim","weapon","enemy","player","esp","target"},
    "item_management":{"inventory","item","items","equip","equipment","loadout"},
    "resource_progression":{"farm","auto","blow","bubble","bubbles","train","resource","capacity"},
    "prestige_progression":{"rebirth","prestige","ascend","reset"},
    "boss_encounters":{"boss","raid","arena"},
    "crafting":{"craft","fuse","forge","enchant","evolve"},
}
ACTION_ROLES={
    "blow":"generate_resource","train":"generate_resource","collect":"collect_resource",
    "sell":"convert_resource","convert":"convert_resource","exchange":"convert_resource",
    "hatch":"acquire_item","open":"acquire_item","purchase":"spend_resource",
    "buy":"spend_resource","upgrade":"spend_resource","claim":"collect_reward",
    "equip":"manage_loadout","unequip":"manage_loadout","unequip-all":"manage_loadout",
    "craft":"transform_item","fuse":"transform_item","rebirth":"prestige",
    "travel":"navigate","teleport":"navigate","attack":"combat_action",
    "shoot":"combat_action","fire":"combat_action","aim":"combat_utility",
}
ACTION_ALIASES={
    "hatch":{"hatch","egg","eggs"},"blow":{"blow","bubble","bubbles"},
    "sell":{"sell","selling"},"purchase":{"buy","purchase","shop"},
    "upgrade":{"upgrade","improve"},"claim":{"claim","reward"},
    "travel":{"travel","teleport","navigate"},"attack":{"attack","combat"},
    "aim":{"aim","aimbot","target"},"equip":{"equip","loadout"},
}
ACTION_BLOCKERS={
    "hatch":["selected_target_identity","interaction_mechanism","mode_semantics",
             "navigation_contract","resource_requirement","observable_result","failure_outcomes"],
    "blow":["interaction_mechanism","capacity_state","observable_result","failure_outcomes"],
    "sell":["interaction_mechanism","capacity_state","sell_location","observable_result","failure_outcomes"],
    "purchase":["selected_target_identity","interaction_mechanism","resource_requirement","failure_outcomes"],
    "upgrade":["selected_target_identity","interaction_mechanism","resource_requirement","failure_outcomes"],
    "travel":["selected_target_identity","navigation_contract","arrival_observation","failure_outcomes"],
    "attack":["target_identity","interaction_mechanism","game_restrictions","failure_outcomes"],
    "aim":["target_identity","camera_contract","visibility_constraints","game_restrictions"],
}
TIER_ORDER={
    "structural_candidate":0,"interaction_observed":1,"temporal_state_correlation":2,
    "observable_outcome_candidate_unverified":3,
}


def _safe_text(value):
    return isinstance(value,str) and 0<len(value)<=MAX_TEXT and all(ord(char)>=32 for char in value)


def _tokens(value):
    if not isinstance(value,str): return set()
    return {item.casefold() for item in re.findall(r"[^\W_]+",value,flags=re.UNICODE)}


def _terminal_name(key):
    terminal=str(key).replace("/",".").split(".")[-1]
    words=re.findall(r"[^\W_]+",terminal,flags=re.UNICODE)
    return " ".join(words[-4:])[:100] or "Observed value"


def _resource_classification(key,name):
    words=_tokens(key)|_tokens(name)
    if words & {"coin","coins","cash","gem","gems","gold","token","tokens","credit","credits","money","currency"}:
        return "currency_candidate"
    if words & {"inventory","count","amount","capacity","slot","slots","ammo","ammunition"}:
        return "inventory_quantity_candidate"
    if words & {"health","damage","strength","agility","level","levels","xp","experience","rebirth","rebirths","score"}:
        return "progression_stat_candidate"
    return "observable_resource_candidate"


def _tier(feature=None,events=None):
    events=events or []
    if any(item.get("observableOutcomeCandidate") is not None for item in events):
        return "observable_outcome_candidate_unverified"
    if any(_changes(item) for item in events): return "temporal_state_correlation"
    if events or (feature and feature.get("interactionEvents",0)>0): return "interaction_observed"
    return "structural_candidate"


def _better(left,right):
    return right if TIER_ORDER[right]>TIER_ORDER[left] else left


def _changes(event):
    candidates=[]
    raw=event.get("stateChanges")
    if isinstance(raw,list): candidates.extend(raw)
    if not candidates and isinstance(event.get("observationWindows"),list):
        for window in event["observationWindows"]:
            if isinstance(window,dict) and isinstance(window.get("stateChanges"),list):
                candidates.extend(window["stateChanges"])
    result=[];seen=set()
    for item in candidates:
        if not isinstance(item,dict): continue
        key=item.get("key") or item.get("path")
        before,after=item.get("before"),item.get("after")
        if (not _safe_text(key) or type(before) not in SCALARS or type(after) not in SCALARS
                or len(str(before))>100 or len(str(after))>100):
            continue
        identity=(key,type(before).__name__,str(before),type(after).__name__,str(after))
        if identity in seen: continue
        seen.add(identity)
        result.append({"key":key,"before":before,"after":after})
        if len(result)>=MAX_CHANGES: break
    return result


def _action(event):
    workflow=event.get("workflow")
    value=workflow.get("action") if isinstance(workflow,dict) else None
    if not _safe_text(value):
        value=event.get("actionKind")
    if not _safe_text(value): return None
    return value.casefold()


def _validate_plan(plan):
    if not isinstance(plan,dict): raise ValueError("gameplay plan must be an object")
    integrity=plan.get("integrity")
    if (not isinstance(integrity,dict) or integrity.get("scanComplete") is not True
            or type(integrity.get("placeId")) is not int or integrity["placeId"]<=0
            or not _safe_text(integrity.get("scanId"))):
        raise ValueError("complete validated scan required")
    features=plan.get("features")
    history=plan.get("observedInteractionHistory",[])
    if not isinstance(features,list) or len(features)>MAX_FEATURES:
        raise ValueError("invalid gameplay feature inventory")
    if not isinstance(history,list) or len(history)>MAX_EVENTS:
        raise ValueError("invalid gameplay interaction history")
    for feature in features:
        if not isinstance(feature,dict) or not _safe_text(feature.get("feature")):
            raise ValueError("invalid gameplay feature")
        for field in ("interactionEvents","observableOutcomeCandidates",
                      "featureStateCorrelations","featureGuiCorrelations"):
            if type(feature.get(field,0)) is not int or feature.get(field,0)<0:
                raise ValueError("invalid gameplay evidence counter")
    for event in history:
        if not isinstance(event,dict): raise ValueError("invalid gameplay event")
        workflow=event.get("workflow")
        if (event.get("outcomeVerified") is True
                or (isinstance(workflow,dict) and workflow.get("verified") is True)):
            raise ValueError("passive gameplay event claims verified outcome")
        candidate=event.get("observableOutcomeCandidate")
        if candidate is not None:
            if (not isinstance(candidate,dict)
                    or candidate.get("classification")!="feature-consistent-observable-change"
                    or any(candidate.get(field) is not False for field in (
                        "sourceAuthenticityVerified","causalityProven",
                        "serverAuthorityVerified","gameplayVerified"))):
                raise ValueError("invalid observable outcome candidate")
    return integrity,features,history


def _systems(features,history):
    by_feature={item["feature"]:item for item in features}
    events_by_feature={name:[] for name in by_feature}
    for event in history:
        name=event.get("featureCandidate")
        if name in events_by_feature: events_by_feature[name].append(event)
    systems={}
    for name,item in sorted(by_feature.items()):
        mapping=FEATURE_SYSTEMS.get(name)
        if mapping is None: continue
        identifier,label=mapping
        events=events_by_feature[name]
        evidence=item.get("evidence")
        readiness=item.get("readiness")
        if (not events and item.get("interactionEvents",0)==0
                and ((isinstance(evidence,dict) and evidence.get("status")=="not-discovered")
                     or (isinstance(readiness,dict) and readiness.get("discovered") is False))):
            continue
        tier=_tier(item,events)
        system=systems.setdefault(identifier,{"id":identifier,"label":label,
            "sourceFeatures":[],"evidenceTier":"structural_candidate",
            "observedInteractions":0,"observableOutcomeCandidates":0,
            "classification":"composable_system_candidate",
            "systemVerified":False,"causalityProven":False,"gameplayVerified":False})
        system["sourceFeatures"].append(name)
        system["evidenceTier"]=_better(system["evidenceTier"],tier)
        system["observedInteractions"]+=item.get("interactionEvents",0)
        system["observableOutcomeCandidates"]+=item.get("observableOutcomeCandidates",0)
    return [systems[identifier] for identifier in sorted(systems)]


def _resources(history):
    collected={}
    for event in history:
        action=_action(event)
        feature=event.get("featureCandidate") if _safe_text(event.get("featureCandidate")) else None
        for change in _changes(event):
            before,after=change["before"],change["after"]
            if type(before) not in (int,float) or type(after) not in (int,float) or before==after:
                continue
            name=_terminal_name(change["key"])
            item=collected.setdefault(name,{"name":name,"sourceKeys":set(),"observedDirections":set(),
                "observedActions":set(),"sourceFeatures":set(),"observationCount":0,
                "classification":_resource_classification(change["key"],name)})
            item["sourceKeys"].add(change["key"])
            item["observedDirections"].add("increase" if after>before else "decrease")
            if action:item["observedActions"].add(action)
            if feature:item["sourceFeatures"].add(feature)
            item["observationCount"]+=1
    result=[]
    for name,item in sorted(collected.items()):
        source_keys=sorted(item["sourceKeys"])
        slug=re.sub(r"[^a-z0-9]+","_",name.casefold()).strip("_")[:40] or "value"
        identity=hashlib.sha256("\n".join(source_keys).encode("utf-8")).hexdigest()[:12]
        result.append({"id":"resource_"+slug+"_"+identity,
            "name":name,"classification":item["classification"],
            "sourceKeys":source_keys,
            "observedDirections":sorted(item["observedDirections"]),
            "observedActions":sorted(item["observedActions"]),
            "sourceFeatures":sorted(item["sourceFeatures"]),
            "observationCount":item["observationCount"],
            "authority":"client_visible","causalityProven":False,"gameplayVerified":False})
    return result


def _actions(history,resources):
    resource_by_key={key:item["name"] for item in resources for key in item["sourceKeys"]}
    grouped={}
    for event in history:
        action=_action(event)
        if action is None: continue
        item=grouped.setdefault(action,{"id":action,"role":ACTION_ROLES.get(action,"observed_action"),
            "sourceFeatures":set(),"paths":set(),"effects":{},"interactionCount":0,
            "evidenceTier":"interaction_observed"})
        item["interactionCount"]+=1
        if _safe_text(event.get("featureCandidate")):item["sourceFeatures"].add(event["featureCandidate"])
        if _safe_text(event.get("path")) and len(item["paths"])<8:item["paths"].add(event["path"])
        item["evidenceTier"]=_better(item["evidenceTier"],_tier(events=[event]))
        for change in _changes(event):
            resource=resource_by_key.get(change["key"])
            if resource is None: continue
            before,after=change["before"],change["after"]
            if type(before) in (int,float) and type(after) in (int,float) and before!=after:
                item["effects"].setdefault(resource,set()).add("increase" if after>before else "decrease")
    result=[]
    for action,item in sorted(grouped.items()):
        result.append({"id":action,"role":item["role"],
            "sourceFeatures":sorted(item["sourceFeatures"]),"observedPaths":sorted(item["paths"]),
            "resourceEffects":[{"resource":name,"directions":sorted(directions)}
                               for name,directions in sorted(item["effects"].items())],
            "interactionCount":item["interactionCount"],"evidenceTier":item["evidenceTier"],
            "classification":"observed_client_interaction",
            "interactionMechanismVerified":False,"causalityProven":False,
            "replayable":False,"gameplayVerified":False})
    return result


def _relationships(actions):
    result=[]
    for action in actions:
        for effect in action["resourceEffects"]:
            for direction in effect["directions"]:
                result.append({"sourceType":"observed_action","sourceId":action["id"],
                    "targetType":"observable_resource","targetId":effect["resource"],
                    "relationship":"temporally_followed_by_"+direction,
                    "evidenceTier":action["evidenceTier"],"causalityProven":False})
    for index,item in enumerate(result):item["id"]=f"relationship_{index:04d}"
    return result


def _loops(actions,resources):
    resource_classes={item["name"]:item["classification"] for item in resources}
    loops=[]
    for action in actions:
        increases={e["resource"] for e in action["resourceEffects"] if "increase" in e["directions"]}
        decreases={e["resource"] for e in action["resourceEffects"] if "decrease" in e["directions"]}
        if increases and decreases:
            loop_id="companion_acquisition" if (action["role"]=="acquire_item" and
                any(resource_classes.get(name)=="inventory_quantity_candidate" for name in increases)) else "resource_conversion"
            loops.append({"id":loop_id,"label":"Companion or item acquisition" if loop_id=="companion_acquisition" else "Resource conversion",
                "stepActionIds":[action["id"]],"inputResources":sorted(decreases),
                "outputResources":sorted(increases),"evidenceTier":action["evidenceTier"],
                "classification":"observed_transition_pattern","completedLoopObserved":False,
                "causalityProven":False,"replayable":False,"gameplayVerified":False})
    generated=[action for action in actions if action["role"] in ("generate_resource","collect_resource")]
    converted=[action for action in actions if action["role"]=="convert_resource"]
    for source in generated:
        source_up={e["resource"] for e in source["resourceEffects"] if "increase" in e["directions"]}
        for target in converted:
            target_down={e["resource"] for e in target["resourceEffects"] if "decrease" in e["directions"]}
            shared=source_up&target_down
            if shared:
                loops.append({"id":"accumulate_and_convert","label":"Accumulate and convert resources",
                    "stepActionIds":[source["id"],target["id"]],"inputResources":[],
                    "intermediateResources":sorted(shared),"outputResources":sorted(
                        e["resource"] for e in target["resourceEffects"] if "increase" in e["directions"]),
                    "evidenceTier":_better(source["evidenceTier"],target["evidenceTier"]),
                    "classification":"cross_interaction_progression_hypothesis",
                    "completedLoopObserved":False,"causalityProven":False,
                    "replayable":False,"gameplayVerified":False})
    unique={}
    for item in loops: unique.setdefault(item["id"],item)
    return [unique[key] for key in sorted(unique)]


def _objectives(systems,resources,actions):
    objectives=[]
    for resource in resources:
        if "increase" in resource["observedDirections"]:
            objectives.append({"kind":"resource_accumulation","label":"Accumulate "+resource["name"],
                "targetIds":[resource["id"]],"evidenceTier":"temporal_state_correlation",
                "classification":"objective_candidate","primaryObjectiveVerified":False})
    if any(system["id"]=="companion_collection" for system in systems) and any(
            action["role"]=="acquire_item" for action in actions):
        objectives.append({"kind":"collection_progression","label":"Acquire collectible companions or items",
            "targetIds":["companion_collection"],"evidenceTier":max(
                (action["evidenceTier"] for action in actions if action["role"]=="acquire_item"),
                key=lambda tier:TIER_ORDER[tier]),"classification":"objective_candidate",
            "primaryObjectiveVerified":False})
    if any(system["id"]=="combat" for system in systems):
        objectives.append({"kind":"combat_progression","label":"Participate in combat encounters",
            "targetIds":["combat"],"evidenceTier":next(
                system["evidenceTier"] for system in systems if system["id"]=="combat"),
            "classification":"objective_candidate","primaryObjectiveVerified":False})
    objectives.sort(key=lambda item:(-TIER_ORDER[item["evidenceTier"]],item["kind"],item["label"]))
    for index,item in enumerate(objectives):item["rank"]=index+1
    return objectives


def _opportunities(systems,actions):
    values=[]
    for system in systems:
        sources=system["sourceFeatures"]
        related=([action for action in actions
                  if any(feature in sources for feature in action["sourceFeatures"])]
                 if sources else [action for action in actions if action["resourceEffects"]])
        tier=system["evidenceTier"]
        if related:
            tier=max([tier]+[item["evidenceTier"] for item in related],key=lambda value:TIER_ORDER[value])
        blockers={"permitted_action_contract","live_failure_validation","clean_stop_behavior"}
        for action in related:blockers.update(ACTION_BLOCKERS.get(action["id"],("interaction_mechanism","observable_result")))
        values.append({"id":system["id"],"label":system["label"],"evidenceTier":tier,
            "observedActionIds":sorted(item["id"] for item in related),
            "status":"blocked_pending_action_contract" if related else "insufficient_interaction_evidence",
            "blockers":sorted(blockers),"implementationReady":False,"liveVerified":False})
    return values


def _request(plan,systems,resources,actions,opportunities):
    request=plan.get("requestedCapability")
    if request is None:return None
    if not _safe_text(request):raise ValueError("invalid requested capability")
    words=_tokens(request)
    matched_systems=sorted(system["id"] for system in systems
        if words&SYSTEM_ALIASES.get(system["id"],set()))
    matched_actions=sorted(action["id"] for action in actions
        if words&ACTION_ALIASES.get(action["id"],{action["id"]}))
    matched_resources=sorted(resource["name"] for resource in resources if words&_tokens(resource["name"]))
    tiers=[system["evidenceTier"] for system in systems if system["id"] in matched_systems]
    tiers.extend(action["evidenceTier"] for action in actions if action["id"] in matched_actions)
    tier=max(tiers,key=lambda value:TIER_ORDER[value]) if tiers else "structural_candidate"
    blockers={"permitted_action_contract","live_failure_validation","clean_stop_behavior"}
    for action in matched_actions:blockers.update(ACTION_BLOCKERS.get(action,()))
    for opportunity in opportunities:
        if opportunity["id"] in matched_systems:blockers.update(opportunity["blockers"])
    if not matched_systems and not matched_actions and not matched_resources:
        status="unsupported_by_current_evidence";blockers.add("matching_client_visible_evidence")
    elif matched_actions:
        status="blocked_pending_action_contract"
    else:
        status="insufficient_interaction_evidence"
    return {"request":request,"matchedSystems":matched_systems,
        "matchedObservedActions":matched_actions,"matchedResources":matched_resources,
        "evidenceTier":tier,"status":status,"blockers":sorted(blockers),
        "implementationReady":False,"runtimeVerified":False,"gameplayVerified":False}


def analyze(plan):
    integrity,features,history=_validate_plan(plan)
    systems=_systems(features,history)
    resources=_resources(history)
    actions=_actions(history,resources)
    if resources and not any(system["id"]=="resource_progression" for system in systems):
        systems.append({"id":"resource_progression","label":"Observable resources and progression state",
            "sourceFeatures":[],"evidenceTier":"temporal_state_correlation",
            "observedInteractions":sum(item["interactionCount"] for item in actions),
            "observableOutcomeCandidates":sum(item["evidenceTier"]=="observable_outcome_candidate_unverified" for item in actions),
            "classification":"composable_system_candidate","systemVerified":False,
            "causalityProven":False,"gameplayVerified":False})
    systems.sort(key=lambda item:item["id"])
    relationships=_relationships(actions)
    loops=_loops(actions,resources)
    objectives=_objectives(systems,resources,actions)
    opportunities=_opportunities(systems,actions)
    result={"schemaVersion":SCHEMA_VERSION,"placeId":integrity["placeId"],
        "scanId":integrity["scanId"],"model":"composable_capabilities","genre":None,
        "objectiveCandidates":objectives,"systems":systems,"resources":resources,
        "observedActions":actions,"progressionRelationships":relationships,
        "progressionLoops":loops,"automationOpportunities":opportunities,
        "requestedCapabilityAssessment":_request(plan,systems,resources,actions,opportunities),
        "summary":{"objectiveCandidates":len(objectives),"systems":len(systems),
            "resources":len(resources),"observedActions":len(actions),
            "progressionRelationships":len(relationships),"progressionLoops":len(loops),
            "implementationReadyOpportunities":0},
        "claims":{"sourceAuthenticityVerified":False,"primaryObjectiveVerified":False,
            "causalityProven":False,"serverAuthorityVerified":False,"replayable":False,
            "runtimeVerified":False,"gameplayVerified":False,"actionOutcomesVerified":False},
        "limitations":["Client-visible evidence only","Names are structural candidates, not mechanics",
            "Temporal state changes do not prove causality","No server-only information or remote payload inference",
            "Automation requires a permitted reviewed action contract and live failure validation"]}
    return result


def validate(document,plan):
    expected=analyze(plan)
    if document!=expected:raise ValueError("gameplay understanding does not match source plan")
    return document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan");parser.add_argument("--output",default="build/gameplay-understanding.json")
    args=parser.parse_args()
    try:
        raw=pathlib.Path(args.plan).read_bytes()
        if len(raw)>20_000_000:raise ValueError("gameplay source plan too large")
        result=analyze(json.loads(raw))
        target=pathlib.Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        print("Gameplay understanding:",target)
        return 0
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        print("GAMEPLAY UNDERSTANDING BLOCKED:",exc,file=sys.stderr);return 2


if __name__=="__main__":sys.exit(main())
