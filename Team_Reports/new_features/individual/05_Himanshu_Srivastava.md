# Report: Himanshu Srivastava

Role: LLM integration and character agents

Project: Off Script: The Last Light of Aether (CSE339 Capstone)

Topic: two new features (Mind View and Team Journal)

Date: 18 November 2026

## The two new features (short)

- **Feature 1: Mind View.** You can look inside a character's head. It shows the options the character had, which one it picked, and who picked it (its rules, the AI, a lesson from a past game, or the player's order). It also shows what the character believes next to what is really true, and its recent memories. On the map, purple bubbles and "ghosts" show where its knowledge is out of date.
- **Feature 2: Team Journal (learning across games).** After every Watch run, a character finds a place where it waited a long time when it could have done something else, and writes a lesson. The next Watch run tests the lesson. If the team finishes sooner or with a better ending, the lesson is kept. If not, it is dropped.

Real result: Run 1 took 330s. Aria learned "decode the symbols myself", and Run 2 took 325s, so the lesson was kept. Her next lesson made Run 3 take 360s, so it was dropped.

## My work

My part was inside the character agents: recording how each decision was made, and making the characters use their lessons.

### 1. Decision trace (for the Mind View)

- Every character repeats: look around, decide, act. I now record each decision:
  - all the options the rules offered;
  - the option that was chosen;
  - who chose it: the rules, the AI, a lesson, or the player's radio order;
  - the reason: the AI's one-line reason, or the lesson's text;
  - the news that caused the choice, for example "Aria sees that the Hidden Forest Trail is open".
- When the AI chooses, its one-line reason is now saved, so the Mind View can show it in quotes.

### 2. Waiting log (for the Team Journal)

- Each time a character starts waiting or is blocked, I record when it started, where it was, and the other options it had.
- When it stops waiting, I record the end time. This log is what the reflection reads after the run.

### 3. Using lessons in the planner

- A lesson says: "in the situation where I would do X, do Y instead".
- The planner uses a lesson **only** if its first choice is X, and Y is one of the valid options right now.
- The order of priority is: the player's orders, then the AI's choice, then a lesson, then the normal rule.
- The first time a lesson is used, the game shows an event: "Aria remembers an earlier game: …".
- A lesson can never create a new action. The rules engine still checks every action.

## How to show it

- In the second Watch run, the pop-up "Aria remembers an earlier game" appears at about 1:08.
- Open Aria's Mind View: "Lesson from a past game" is shown, with "Wait at the temple" as the rules' first choice and "decode the symbols myself" chosen.

## Testing

- Tests check that the trace marks exactly one chosen option, that the AI's reason appears, that player orders show as "your radio order", and that a lesson is used once and makes the run faster.
- All 217 backend tests pass.

## Files I worked on

- backend/app/agents/character_agent.py (decision trace, waiting log, "lesson applied" event)
- backend/app/agents/planner.py (returns the options; applies lessons)
- backend/app/models/mind.py (new data: trace, waiting log, lessons)
- backend/app/services/run_manager.py (saving the AI's reason)
