# What changes when the twin controls real hardware

The simulation makes one useful promise: each forward command passes through
a visible safety policy. Real hardware needs a stronger promise, supported
by measurements and failure tests. A stopped animation is not evidence that
a physical robot can stop in time.

## The sim-to-real gap

This twin knows its position and obstacle geometry exactly. A low-cost robot
does not. Wheels slip, batteries discharge, floors vary, motors respond
unevenly, and payload changes motion. A requested metre is an intention.
Encoders and external measurements tell us what actually happened.

The point model also ignores body size. A sensor can report a clear centreline
while a wheel, bumper, or corner clips an obstacle. Before commanding hardware,
model the footprint and check the swept area of both movement and turns.

Start by comparing predicted and measured straight-line distance and turn
angle. Record repeatability as well as average error. A model that is usually
accurate but occasionally far wrong needs conservative operating limits.

## Latency changes stopping distance

In this simulation, sensing and stopping are immediate. Hardware has sensor
sampling delays, transport delays, scheduling delays, and motor response time.
The robot continues moving while those delays accumulate.

A useful first approximation is:

required clearance = body allowance + uncertainty allowance
                   + speed × reaction delay + braking distance

This is a starting model, not a validated safety calculation. Braking distance
must be measured across the relevant speeds, surfaces, loads, and battery
conditions. The demo's fixed 0.40 metre margin is not a hardware specification.

Timestamp sensor readings. Reject stale data. Keep the fast stop decision close
to the robot, and use a watchdog that stops motion when commands or heartbeats
expire. A lost connection must not leave the last motor command running.

## Sensor noise is part of the system

Real range sensors can miss narrow objects, reflect poorly from some surfaces,
or return invalid measurements. Their fields of view differ from ideal rays.

Log raw readings alongside filtered readings. Test dropout, frozen values,
out-of-range values, and contradictory sensors. Filtering can reduce noise,
but it also adds delay. An invalid or stale reading must not silently become
"the path is clear."

The twin should eventually simulate these failures so the same controller can
be exercised before a robot moves.

## Safety belongs in the platform layer

A prompt parser should express intent. It should not decide whether motion is
safe. The same policy must apply to prompts, scripts, dashboards, and future
planners.

Put command limits, sensor freshness checks, motion authorization, and stop
handling below every command interface. Keep the lowest-level motor interface
private to that path. On hardware, back this with a local watchdog and a stop
mechanism that does not depend on the language interface or network connection.

Log why a command was refused or interrupted. Never report completion when a
safety stop prevented completion. Require a deliberate new command to resume.

## What I would test first on a low-cost robot

1. Raise the wheels off the ground. Verify motor direction, bounded commands,
   the watchdog, and an accessible physical stop.
2. In a clear test area at low speed, measure straight travel and turns using
   an external reference. Repeat at different battery levels.
3. Measure stopping distance and end-to-end response delay. Use the worst
   observed results to inform the next test limits.
4. Approach a large, detectable obstacle slowly with generous clearance.
   Verify refusal, stopping, event logs, and explicit restart behaviour.
5. Inject stale readings, sensor disconnection, process failure, and lost
   communication. Verify that the robot stops and stays stopped.
6. Test body corners, turning clearance, and difficult surfaces before
   increasing speed or introducing more complex routes.

I would keep the first hardware scope small: one robot, one controlled area,
low speed, and a person ready to stop it. The next milestone is a measured,
repeatable agreement between commanded motion, predicted motion, and what
the robot actually does.
