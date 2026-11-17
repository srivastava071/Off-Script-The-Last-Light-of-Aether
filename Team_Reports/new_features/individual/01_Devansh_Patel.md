# Report: Devansh Patel

Role: Backend and API

Project: Off Script: The Last Light of Aether (CSE339 Capstone)

Topic: two new features (Mind View and Team Journal)

Date: 18 November 2026

## The two new features (short)

- **Feature 1: Mind View.** You can look inside a character's head. It shows the options the character had, which one it picked, and who picked it (its rules, the AI, a lesson from a past game, or the player's order). It also shows what the character believes next to what is really true, and its recent memories. On the map, purple bubbles and "ghosts" show where its knowledge is out of date.
- **Feature 2: Team Journal (learning across games).** After every Watch run, a character finds a place where it waited a long time when it could have done something else, and writes a lesson. The next Watch run tests the lesson. If the team finishes sooner or with a better ending, the lesson is kept. If not, it is dropped.

Real result: Run 1 took 330s. Aria learned "decode the symbols myself", and Run 2 took 325s, so the lesson was kept. Her next lesson made Run 3 take 360s, so it was dropped.

## My work

My part was to connect both new features to the server, so the game screen can show them.

### 1. Mind View: sending the character's mind to the screen

- The game screen asks the server for the "state" of the run many times a minute.
- I added a new part called **mind** to every character in that state.
- The mind contains: the character's last decision, what it believes compared with reality, its memories and its lessons.
- The screen does not calculate anything itself. It only shows what the server sends.

### 2. Team Journal: new API

- I added two new addresses (endpoints) to the server:
  - **GET /api/journal**: returns all lessons and all finished runs (the learning curve).
  - **POST /api/journal/reset**: forgets every lesson ("Forget everything" button).
- These do not need a run token, because the journal belongs to the whole team, not to one run.

### 3. Connecting the journal to the game

- When a run finishes, the server now records it in the journal **exactly once**, even if the page is refreshed.
- When a new run starts, the server gives each character the lessons it should use.
- If the journal ever has a problem, the finished game is not affected. The error is only written to the log.

## How to show it

- Open http://localhost:8000/docs. The new "journal" section is listed there.
- After a Watch run, open http://localhost:8000/api/journal to see the lesson in plain data.

## Testing

- An automatic test plays two Watch runs through the API, checks that the lesson is "trying" and then "kept", resets the journal, and checks the game plays like the first time again.
- All 217 backend tests pass.

## Files I worked on

- backend/app/api/journal.py (new journal endpoints)
- backend/app/services/run_manager.py (record finished runs, load lessons for new runs)
- backend/app/schemas/views.py (the "mind" part of each character)
- backend/app/main.py (adding the new endpoints to the server)
