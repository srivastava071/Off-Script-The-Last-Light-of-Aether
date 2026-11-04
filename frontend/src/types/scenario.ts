import type { CharacterId, LocationView, Objective } from "./api";

export interface CharacterProfile {
  id: CharacterId;
  name: string;
  title: string;
  personality: string;
  primary_goal: string;
  abilities: string[];
  restrictions: string[];
  speed_multiplier: number;
  carry_capacity: number;
  can_carry_heavy: boolean;
  color: string;
}

export interface Scenario {
  title: string;
  backstory: string;
  characters: CharacterProfile[];
  locations: LocationView[];
  objectives: Objective[];
}

export const prettyAbility = (a: string) => a.replace(/_/g, " ");
