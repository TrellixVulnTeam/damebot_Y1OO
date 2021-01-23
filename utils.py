import nonebot
from nonebot import on_command
from nonebot.adapters import Bot, Event
from nonebot.matcher import Matcher
from nonebot.typing import T_State
import asyncio
from nonebot.log import logger
from random import choice, randint
import re
import shlex

def start_end_alternative(first_start=True):
    if first_start:
        yield 0
    i = 1
    while True:
        yield from [-i, i]
        i += 1

def fill_in_generate():
    return "\n" + choice(["いぉ","など"]) * randint(2,3) + "." * randint(3,6) + "\n"

def dame(err: str):
    return f"""{choice(['ダメ', '駄目'])}{choice(['です', ''])}{"！" * randint(0,5)}
  {err}      
""".strip()

async def summary(s: str, limit=50, keep_first=True, fill_in_gen=fill_in_generate):
    if len(s) > limit:
        lines = s.splitlines(keepends=True)
        if len(lines) <= 1:
            words = [x + " " for x in s.split()]
            if len(words) <= 1:
                chinese_phrases = re.split("|".join(f"(?<={x})" for x in ["，","。","；"]), s)
                units = chinese_phrases
            else:
                units = words
        else:
            units = lines
        starts = []
        ends = []
        collected_counts = 0
        for i in start_end_alternative(keep_first):
            current = starts if i >= 0 else ends
            unit = units[i]
            current.append(unit)
            collected_counts += len(unit)
            if collected_counts > limit:
                break
        ends.reverse()
        return ("".join(starts) + fill_in_gen() + "".join(ends)).strip()
    else:
        return s
    
async def execute(cmd):
    logger.info(f"trying to execute '{cmd}'")
    proc = await asyncio.create_subprocess_exec(
        *shlex.split(cmd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    logger.debug(f"'{cmd}' process created.")
    stdout, stderr = await proc.communicate()
    logger.debug(f"got stdout \nf{stdout}")
    logger.debug(f"got stderr \nf{stderr}")
    if proc.returncode == 0:
    # also can use proc.returncode
        output = stdout.decode()
    else:
        err_short = await summary(stderr.decode())
        output = dame(err_short)
    return output

async def multi_execute(*extra):
    result = await execute(" ".join(x.strip() for x in extra))
    return result

async def plain_string(_, doc):
    return doc

import inspect
class CommandBuilder:
    def __init__(
        self, cmd, 
        *cmd_in_dice, 
        help_short="--version", 
        help_short_text=None, 
        help_long="--help", 
        help_long_text=None, 
        help_async_factory=None, 
        help_short_async_factory=None, 
        help_long_async_factory=None, 
        sub_commands=None, 
        priority=100, 
        **extra_kwargs):
        _locals = locals()
        _spec = inspect.getfullargspec(self.__init__)
        _args = [_locals[x] for x in _spec.args] + list(_locals[_spec.varargs])
        _kwargs = {x:_locals[x] for x in _spec.kwonlyargs}
        _kwargs.update(_locals[_spec.varkw])
        if sub_commands is None:
            sub_commands = []
        else:
            if isinstance(sub_commands, str, CommandBuilder, dict):
                sub_commands = [sub_commands]
            new_sub_commands = []
            for sub_command in sub_commands:
                if isinstance(sub_command, str):
                    sub = sub_command
                    args = [" ".join([x, sub]) for x in _args]
                    kwargs = _kwargs.copy()
                    kwargs["sub_commands"] = None
                    sub_command = CommandBuilder(*args, **kwargs)
                elif isinstance(sub_command, dict):
                    sub_dict_commands = []
                    for sub, subsub in sub_command.items():
                        args = [" ".join([x, sub_command]) for x in _args]
                        kwargs = _kwargs.copy()
                        kwargs["sub_commands"] = subsub
                        sub_dict_commands.append(CommandBuilder(*args, **kwargs))
                    sub_command = sub_dict_commands
                new_sub_commands.append(sub_command)
        if len(cmd_in_dice) == 0:
            cmd_in_dice = [cmd]
        if help_async_factory is None:
            help_async_factory = multi_execute
        if help_short_async_factory is None:
            help_short_async_factory = help_async_factory if help_short_text is None else plain_string
        if help_long_async_factory is None:
            help_long_async_factory = help_async_factory if help_long_text is None else plain_string  
        self.cmd = cmd
        self.cmd_in_dice = cmd_in_dice
        self.help_short = help_short
        self.help_long = help_long
        self.help_short_async_factory = help_short_async_factory
        self.help_long_async_factory = help_long_async_factory
        self.sub_commands = sub_commands
        self.priority = priority
        self.extra_kwargs = extra_kwargs

    def build(self) -> Matcher:
        main_command, *aliases = [x + " " for x in self.cmd_in_dice]
        aliases = set(aliases)
        matcher = on_command(main_command, aliases=aliases, priority=self.priority, **self.extra_kwargs)
        @matcher.handle()
        async def cmd_handler(bot: Bot, event: Event, state: T_State, matcher: Matcher):
            # get real command content
            logger.debug(f"event: {event}")
            logger.debug(f"state: {state}")
            command_text = event.get_message().extract_plain_text().strip()
            logger.debug(f"got command text '{command_text}'")
            cmd = " ".join([self.cmd, command_text])
            output = await execute(cmd)
            await matcher.send(output)
        matcher.command_builder = self
        return matcher



    