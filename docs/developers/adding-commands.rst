Adding Commands
===============

Kamaki commands are implemented as python classes, decorated with a special decorator called *command*. This decorator is a method of kamaki.cli that adds a new command in a CommandTree structure (kamaki.cli.commant_tree). The later is used by interfaces to manage kamaki commands.

In the following, a set of kamaki commands will be implemented::

    mygrp1 list all                         //show a list
    mygrp1 list details [--match=<>]        //show list of details
    mygrp2 list all [regular expression] [-l]       //list all subjects
    mygrp2 info <id> [name]      //get information for subject with id

There are two command sets to implement, namely mygrp1 and mygrp2. The first will contain two commands, namely list-all and list-details. The second one will also contain two commands, list-all and info. To avoid ambiguities, command names should rather be prefixed with the group they belong to, e.g. mygrp1-list-all and mygrp2-list-all.

The first command has the simplest possible syntax: no parameters, no runtime arguments. The second accepts an optional runtime argument with a value. The third features an optional argument and an optional runtime flag argument. The last is an example of a command with an obligatory and an optional argument.

Samples of the expected behavior in one-command mode are following:

.. code-block:: console

    $kamaki mygrp1
        mygrp1 description

        Options
         - - - -
        list
    $ kamaki mygrp1 list
        Syntax Error

        Options
         - - - -
        all        show a list
        details     show a list of details
    $ kamaki mygrp1 list all
        ... (mygrp1 client method is called) ...
    $ kamaki mygrp2 list all 'Z[.]' -l
        ... (mygrp2 client method is called) ...
    $

The above example will be used throughout the present guide for clarification purposes.

The CommandTree structure
-------------------------

CommandTree manages a command by its path. Each command is stored in multiple nodes on the tree, so that the last term is a leaf and the route from root to that leaf represents the command path. For example the commands *store upload*, *store list* and *store info* are stored together as shown bellow::

    - store
    ''''''''|- info
            |- list
            |- upload

The example used in the present, should result to the creation of two trees::

    - mygrp1
    ''''''''|- list
            '''''''|- all
                   |- details

    - mygrp2
    ''''''''|- list
            '''''''|- all
            |- info

Each command group should be stored on a different CommandTree. For that reason, command specification modules should contain a list of CommandTree objects, named *_commands*

A command group information (name, description) is provided at CommandTree structure initialization:

.. code-block:: python

    _mygrp1_commands = CommandTree('mygrp', 'mygrp1 description')
    _mygrp2_commands = CommandTree('mygrp', 'mygrp2 description')

    _commands = [_mygrp1_commands, _mygrp2_commands]

The command decorator
---------------------

The *command* decorator mines all the information necessary to build a command specification which is then inserted in a CommanTree instance::

    class code  --->  command()  -->  updated CommandTree structure

Kamaki interfaces make use of this CommandTree structure. Optimizations are possible by using special parameters on the command decorator method.

.. code-block:: python

    def command(cmd_tree, prefix='', descedants_depth=None):
    """Load a class as a command
        @cmd_tree is the CommandTree to be updated with a new command
        @prefix of the commands allowed to be inserted ('' for all)
        @descedants_depth is the depth of the tree descedants of the
            prefix command.
    """

Creating a new command specification set
----------------------------------------

A command specification developer should create a new module (python file) with as many classes as the command specifications to be offered. Each class should be decorated with *command*.

.. code-block:: python

    ...
    _commands = [_mygrp1_commands, _mygrp2_commands]

    @command(_mygrp1_commands)
    class mygrp1_list_all():
        ...

    ...

A list of CommandTree structures must exist in the module scope, with the name _commands, as shown above. Different CommandTree objects correspond to different command groups.

Get command description
-----------------------

The description of each command is the first line of the class commend. The following declaration of *mygrp2-info* command has a "*get information for subject with id*" description.

.. code-block:: python

    ...
    @command(_mygrp2_commands)
    class mygrp2_info()
        """get information for subject with id"""
        ...

Declare run-time argument
-------------------------

The argument mechanism allows the definition of run-time arguments. Some basic argument types are defined at the `argument module <cli.html#module-kamaki.cli.argument>`_, but it is not uncommon to extent these classes in order to achieve specialized type checking and syntax control (e.g. at `pithos_cli module <cli.html#module-kamaki.cli.commands.pithos_cli>`_).

To declare a run-time argument on a specific command, the object class should initialize a dict called *arguments* , where Argument objects are stored. Each argument object is a possible run-time argument. Syntax checking happens at client level, while the type checking is implemented in the Argument code (thus, many different Argument types might be needed).

.. code-block:: python

    from kamaki.cli.argument import ValueArgument
    ...

    @command(_mygrp1_commands)
    class mygrp1_list_details():
        """list of details"""

        def __init__(self, global_args={})
            global_args['match'] = ValueArgument(
                'Filter results to match string',
                '--match')
            self.arguments = global_args

The main method and command parameters
--------------------------------------

The command behavior for each command / class is coded in *main*. The parameters of *main* method defines the command parameters part of the syntax. In specific::

    main(self, param)                   - obligatory parameter
    main(self, param=None)              - optional parameter
    main(self, param1, param2=42)       - <param1> [param2]
    main(self, param1____param2)        - <param1:param2>
    main(self, param1____param2=[])     - [param1:param2]
    main(self, param1____param2__)      - <param1[:param2]>
    main(self, param1____param2__='')   - [param1[:param2]]
    main(self, *args)                   - arbitary number of params [...]
    main(self, param1____param2, *args) - <param1:param2> [...]

The information that can be mined by *command* for each individual command is presented in the following:

.. code-block:: python
    :linenos:

    from kamaki.cli.argument import FlagArgument
    ...

    _commands = [_mygrp1_commands, _mygrp2=commands]
    ...

    @command(_mygrp2_commands)
    class mygrp2_list_all(object):
        """List all subjects"""

        def __init__(self, global_args={}):
            global_args['list'] = FlagArgument(
                'detailed list',
                '-l,
                False)

            self.arguments = global_args

        def main(self, reg_exp=None):
            ...

This will load the following information on the CommandTree:

* Syntax (from lines 8,12,19): mygrp list all [reg exp] [-l]
* Description (form line 9): List all subjects
* Arguments help (from line 13,14): -l: detailed list

Letting kamaki know
-------------------

Kamaki will load a command specification *only* if it is set as a configurable option. To demonstrate this, let the command specifications coded above be stored in a file named *grps.py*.

The developer should move file *grps.py* to kamaki/cli/commands, the default place for command specifications, although running a command specification from a different path is also a kamaki feature.

The user has to use a configuration file where the following is added:
::

    [mygrp1]
    cli=grps

    [mygrp2]
    cli=grps

or alternatively:

.. code-block:: console

    $ kamaki config set mygrp1.cli = grps
    $ kamaki config set mygrp2.cli = grps

Command specification modules don't need to live in kamaki/cli/commands, although this is suggested for uniformity. If a command module exist in another path::

    [mygrp]
    cli=/another/path/grps.py

Summary: create a command set
-----------------------------

.. code-block:: python

    #  File: grps.py

    from kamaki.cli.command_tree import CommandTree
    from kamaki.cli.argument import ValueArgument, FlagArgument
    ...


    #  Initiallize command trees

    _mygrp1_commands = CommandTree('mygrp', 'mygrp1 description')
    _mygrp2_commands = CommandTree('mygrp', 'mygrp2 description')

    _commands = [_mygrp1_commands, _mygrp2_commands]


    #  Define command specifications


    @command(_mygrp1_commands)
    class mygrp1_list_all():
        """show a list"""

        arguments = {}

        def main(self):
            ...


    @command(_mygrp1_commands)
    class mygrp1_list_details():
        """show list of details"""

        arguments = {}

        def __init__(self, global_args={})
            global_args['match'] = ValueArgument(
                'Filter results to match string',
                '--match')
            self.arguments = global_args

        def main(self):
            ...
            match_value = self.arguments['list'].value
            ...


    @command(_mygrp2_commands)
    class mygrp2_list_all():
        """list all subjects"""

        arguments = {}

        def __init__(self, global_args={})
            global_args['match'] = FlagArgument('detailed listing', '-l')
            self.arguments = global_args

        def main(self, regular_expression=None):
            ...
            detail_flag = self.arguments['list'].value
            ...
            if detail_flag:
                ...
            ...
            if regular_expression:
                ...
            ...


    @command(_mygrp2_commands)
    class mygrp2_info():
        """get information for subject with id"""

        arguments = {}

        def main(self, id, name=''):
            ...