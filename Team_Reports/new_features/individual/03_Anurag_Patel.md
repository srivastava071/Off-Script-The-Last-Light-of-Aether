# Report: Anurag Patel

Role: Story design, goal tracking, adaptation logic and endings

Project: Off Script: The Last Light of Aether (CSE339 Capstone)

Topic: two new features (Mind View and Team Journal)

Date: 18 November 2026

## The two new features (short)

- **Feature 1: Mind View.** You can look inside a character's head. It shows the options the character had, which one it picked, and who picked it (its rules, the AI, a lesson from a past game, or the player's order). It also shows what the character believes next to what is really true, and its recent memories. On the map, purple bubbles and "ghosts" show where its knowledge is out of date.
- **Feature 2: Team Journal (learning across games).** After every Watch run, a character finds a place where it waited a long time when it could have done something else, and writes a lesson. The next Watch run tests the lesson. If the team finishes sooner or with a better ending, the lesson is kept. If not, it is dropped.

Real result: Run 1 took 330s. Aria learned "decode the symbols myself", and Run 2 took 325s, so the lesson was kept. Her next lesson made Run 3 take 360s, so it was dropped.

## My work

My part was the "thinking" behind the Team Journal: how a character finds a lesson, and how we decide if a lesson is good.

### 1. Finding a lesson (reflection)

- After a Watch run, I look at each character's waiting log.
- A wait counts only if it lasted **30 seconds or more** and the character's rules offered **another option** at that time.
- Each such option becomes a possible lesson. The longest wait is tried first.
- Example: Aria waited 110s at the temple, while "decode the symbols myself" was possible. Lesson: "Last time I waited 110s at the Temple Entrance. Next time: Meera is not here; puzzle out the symbols myself."

### 2. Deciding if a lesson helped (the judge)

- First the ending is compared, from best to worst: The Light Returns, An Unexpected Route, A Costly Victory, The Last Storm.
- If the ending is the same, the faster run is better.
- A lesson is **kept** only if the run that used it did better. Otherwise it is **dropped**, with the reason written in words, for example "It made things worse: 35s slower."
- If the situation never came up in the run, the lesson is dropped, because it could not be tested.

### 3. Rules that keep it clean

- Only **one** lesson is tested at a time, so we know which lesson caused the change.
- If a lesson is dropped, that run does not create a new lesson, because it was played with a bad idea.
- New lessons are tested only in Watch runs. Game Mode teammates use kept lessons only, because a player changes too much for a fair test.

### 4. For the Mind View

- I decided which plans count as "waiting" (waiting or blocked) and which count as normal progress, so the waiting log is correct.

## How to show it

- Play two Watch runs. After the second, the ending screen says: "Aria tried a lesson. It helped: the beacon was lit 5s sooner (325s instead of 330s). Lesson kept."

## Testing

- Tests check that the reflection finds Aria's 110s wait first, that the judge keeps only real improvements, and that the full loop keeps one lesson and drops the next.
- All 217 backend tests pass.

## Files I worked on

- backend/app/agents/learning.py (reflection, ending ranking, judge)
- backend/app/services/journal.py (the order of the steps after a run)
