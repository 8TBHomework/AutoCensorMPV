AutoCensorMPV
-------------

# Requirements
- mpv
- python3
- python-mpv
- nudenet
- PIL

# Run with pipenv
You need python-pipenv for this.

```shell
$ pipenv sync
$ pipenv shell
(venv) $ python main.py play <filename>
```


# Usage
```shell
$ python main.py -h  # global help
$ python main.py play -h  # help for playing
$ python main.py info -h  # help for info
$ python main.py play <file>  # play video at <file>
$ python main.py -m base play <file>  # play video at <file> with base model selected ("default" model has better accuracy)
$ python main.py play -c EXPOSED_BELLY -c COVERED_FEET <file> # just censor belly and covered feet
$ python main.py info -l  # list available labels (to use then with -c)
```

# License
GPL-3.0-or-later
