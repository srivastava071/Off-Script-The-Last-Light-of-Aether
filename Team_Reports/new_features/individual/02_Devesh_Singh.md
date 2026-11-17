# Report: Devesh Singh

Role: Database and simulation loop

Project: Off Script: The Last Light of Aether (CSE339 Capstone)

Topic: two new features (Mind View and Team Journal)

Date: 18 November 2026

## The two new features (short)

- **Feature 1: Mind View.** You can look inside a character's head. It shows the options the character had, which one it picked, and who picked it (its rules, the AI, a lesson from a past game, or the player's order). It also shows what the character believes next to what is really true, and its recent memories. On the map, purple bubbles and "ghosts" show where its knowledge is out of date.
- **Feature 2: Team Journal (learning across games).** After every Watch run, a character finds a place where it waited a long time when it could have done something else, and writes a lesson. The next Watch run tests the lesson. If the team finishes sooner or with a better ending, the lesson is kept. If not, it is dropped.

Real result: Run 1 took 330s. Aria learned "decode the symbols myself", and Run 2 took 325s, so the lesson was kept. Her next lesson made Run 3 take 360s, so it was dropped.

## My work

My part was to store everything the new features need, and to make sure the test of a lesson is fair.

### 1. Storing the decision trace and waiting log

- Each character's mind now also saves its last decision (the trace) and a list of times it was waiting (the waiting log).
- These are saved with the run, like the rest of the game, so a refreshed page or a restarted server keeps them.
- Old saved runs still load, because the new fields have default values.

### 2. New database tables for the Team Journal

- **lessons**: one row per lesson. It stores the character, the lesson text, the reason it was written, its status (trying, kept or dropped), the result of the run it was learned in, and the result of the run that tested it.
- **journal_runs**: one row per finished run, with its ending, its time and a short note. This is the data for the learning curve.
- I wrote the functions to add, update, list and reset these tables.

### 3. Making the test fair

- A Watch run is **deterministic**: with the same lessons, it plays exactly the same every time.
- I checked this: the same Watch run always ends at 330s without lessons, and at 325s with Aria's kept lesson.
- Because of this, any difference between two runs comes from the lesson, not from luck.

## How to show it

- Play a Watch run to the end, then open the main menu. The Team Journal shows the run and the lesson, read from the database.
- Restart the server: the lessons are still there.

## Testing

- A test checks that each finished run is recorded only once.
- A test plays four Watch runs in a row and checks the times: 330s, 325s, then slower, then 325s again.
- All 217 backend tests pass.

## Files I worked on

- backend/app/persistence/tables.py (new tables: lessons, journal_runs)
- backend/app/persistence/repository.py (functions to read and write them)
- backend/app/engine/run.py (giving lessons to the characters when a run is created)
