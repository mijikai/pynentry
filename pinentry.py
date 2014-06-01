#!/usr/bin/env python3
import os
import re
import subprocess


class PinentryError(Exception):
    def __init__(self, error_code, message):
        self._error_code = error_code
        self._message = message

class Pinentry:
    _parameters = {
            'description'         : 'SETDESC',
            'prompt'              : 'SETPROMPT',
            'title'               : 'SETTITLE',
            'ok_button_text'      : 'SETOK',
            'cancel_button_text'  : 'SETCANCEL',
            'error_text'          : 'SETERROR',
            # 'quality_bar_tooltip' : 'SETQUALITYBAR_TT',
            'ttyname'             : 'OPTION ttyname',
            'ttytype'             : 'OPTION ttytype',
            'lc_ctype'            : 'OPTION lc-ctype',
    }

    def __init__(self, binary_path='pinentry', global_grab=True, display=None):
        self._parameter_values = {}
        for key in self._parameters:
            self._parameter_values[key] = None
        if display is None:
            display = os.environ.get('DISPLAY')
        proc = [binary_path]
        if not global_grab:
            proc.append('--no-global-grab')
        if display is not None:
            proc.append('--display')
            proc.append(display)
        self._pinentry = subprocess.Popen(proc,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                universal_newlines=True)
        last_line = self._read_response()[-1]
        if last_line.startswith('OK'):
            return
        elif last_line.startswith('ERR'):
            error_code, message = self._parse_error(last_line)
            raise PinentryError(error_code, message)

    def __del__(self):
        self._pinentry.terminate()

    def _set_pinentry(self, attribute, value=None):
        if value is None:
            return
        last_line = self._input('{} {}'.format(attribute, value))[-1]
        if last_line.startswith('OK'):
            return
        elif last_line.startswith('ERR'):
            error_code, message = self._parse_error(last_line)
            raise PinentryError(error_code, message)

    def _read_response(self):
        response = []
        for line in self._pinentry.stdout:
            matcher = re.match('^(OK|ERR).*', line)
            response.append(line)
            if matcher is not None:
                break
        return response

    def _parse_error(self, line):
        matcher = re.match(r'ERR\s+(\d+)\s+(.*)', line)
        if matcher is None:
            return
        return matcher.group(1), matcher.group(2)

    def _writeline_to_pinentry_stdin(self, text):
        self._pinentry.stdin.write(text + '\n')
        self._pinentry.stdin.flush()

    def _input(self, text):
        self._writeline_to_pinentry_stdin(text)
        return self._read_response()

    def ask_for_pin(self):
        for line in self._input('GETPIN'):
            matcher = re.match('^D (.*)', line)
            if matcher is not None:
                return matcher.group(1)
            error = self._parse_error(line)
            if error is not None:
                error_code, message = error
                raise PinentryError(error_code, message)

    def ask_for_confirmation(self):
        last_line = self._input('CONFIRM')[-1]
        if last_line.startswith('OK'):
            return True
        elif last_line.startswith('ERR'):
            error_code, message = self._parse_error(last_line)
            if message == 'canceled':
                return False

    def show_message(self):
        last_line = self._input('MESSAGE')[-1]
        if last_line.startswith('OK'):
            return
        elif last_line.startswith('ERR'):
            error_code, message = self._parse_error(last_line)
            raise PinentryError(error_code, message)


def _create_property_for_parameter(parameter):
    def getter(self):
        return self._parameter_values[parameter]
    def setter(self, value):
        self._parameter_values[parameter] = value
        self._set_pinentry(self._parameters[parameter], value)
    return property(getter, setter)

for key in Pinentry._parameters:
    setattr(Pinentry, key, _create_property_for_parameter(key))


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='Run pinentry program')

    group = parser.add_mutually_exclusive_group(required=True)
    for pinentry_action in ['ask_for_pin', 'ask_for_confirmation',
            'show_message']:
        arg_name = '--{}'.format(pinentry_action.replace('_', '-'))
        action_method = getattr(Pinentry, pinentry_action)
        group.add_argument(arg_name, const=action_method, action='store_const',
                dest='__pinentry_action')

    for param in Pinentry._parameters:
        arg_name = '--{}'.format(param.replace('_', '-'))
        parser.add_argument(arg_name)

    args = parser.parse_args()
    pinentry_action_method = args.__pinentry_action
    del args.__pinentry_action

    pinentry = Pinentry()
    for param, value in vars(args).items():
        setattr(pinentry, param, value)
    ret = pinentry_action_method(pinentry)
    if ret in [True, False]:
        sys.exit(int(not ret))
    elif ret is not None:
        print(ret)


if __name__ == '__main__':
    main()
