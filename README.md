

<!-- GENERATED README FILE. DO NOT EDIT.    -->
<!-- source in worm-assignment-text/        -->

# Mandatory Assignment 2: The Worm

UiT INF-3203, Spring 2022 \
Vetle Hofsøy-Woie, Ragnar Helgaas

**Due date: Wednesday May 04 at 14:15**

## Contents

-   [How to run](#how-to-run)
-   [Endpoints](#endpoints)

## Also in This Repository

- [`worm_gate/`](worm_gate/) --- Code for the worm gates
- [`python_zip_example/`](python_zip_example/) --- An example
    of how to package a Python project into a single executable
- [`worm`](worm/) --- Module for the worm servers
## How to run

To "compile" the python module into an executable, run the following line from the root directory of this repository

```python_zip_example/make_python_zip_executable.sh worm```

Open wormgates in any way you like, then you can upload the executable with

```curl -X POST 'http://[wormgate_address]:[wormgate_port]/worm_entrance?args=[wormgate_address]:[wormgate_port]&args=[inital size of worm]' --data-binary @worm.bin```

## Endpoints
These requests must be targeted at the worm and not the gate, all worms run on port 64210.

Change size of worm network, can be requested from any worm in the network.

```[POST] /change_size/{new size}```

Get current leader of worm.

```[GET] /benchmark_leader```

Kill all worms in the network. Leader will systematicly kill all worms, then commit suicide.

```[POST] /kill_all```




