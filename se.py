#!/usr/bin/env python

import argparse
import json
import logging
import re
import subprocess
import time
import six
import global_params
from symbolic_execution import sym_exec
from symbolic_execution.utils import run_command
from symbolic_execution.input_helper import InputHelper


def cmd_exists(cmd):
    """Check the command in system's PATH

    Args:
        cmd (_type_): given command

    Returns:
        bool: command installed or not
    """
    return (
        subprocess.call(
            "type " + cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        == 0
    )


def compare_versions(version1, version2):
    """Compare two given versions

    Args:
        version1 (_type_): one version
        version2 (_type_): the other version
    """

    def normalize(v):
        return [int(x) for x in re.sub(r"(\.0+)*$", "", v).split(".")]

    version1 = normalize(version1)
    version2 = normalize(version2)
    if six.PY2:
        return cmp(version1, version2)
    else:
        return (version1 > version2) - (version1 < version2)


def has_dependencies_installed():
    """Checks whether all the necessary dependencies are installed

    Returns:
        bool: whether dependencies are installed
    """
    try:
        import z3
        import z3.z3util

        z3_version = z3.get_version_string()
        tested_z3_version = "4.8.13"
        # if compare_versions(z3_version, tested_z3_version) > 0:
        #     logging.warning(
        #         "You are using an untested version of z3. %s is the officially tested version" % tested_z3_version)
    except e:
        logging.critical(e)
        logging.critical(
            "Z3 is not available. Please install z3 from https://github.com/Z3Prover/z3."
        )
        return False

    if not cmd_exists("evm"):
        logging.critical(
            "Please install evm from go-ethereum and make sure it is in the path."
        )
        return False
    else:
        cmd = "evm --version"
        out = run_command(cmd).strip()
        evm_version = re.findall(r"evm version (\d*.\d*.\d*)", out)[0]
        tested_evm_version = "1.10.21"
        if compare_versions(evm_version, tested_evm_version) > 0:
            logging.warning(
                "You are using evm version %s. The supported version is %s"
                % (evm_version, tested_evm_version)
            )

    if not cmd_exists("solc"):
        logging.critical(
            "solc is missing. Please install the solidity compiler and make sure solc is in the path."
        )
        return False
    else:
        cmd = "solc --version"
        out = run_command(cmd).strip()
        solc_version = re.findall(r"Version: (\d*.\d*.\d*)", out)[0]
        tested_solc_version = "0.8.16"
        if compare_versions(solc_version, tested_solc_version) > 0:
            logging.warning(
                "You are using solc version %s, The latest supported version is %s"
                % (solc_version, tested_solc_version)
            )

    return True


def analyze_bytecode():
    global args

    helper = InputHelper(source=args.source, evm=args.evm)
    inp = helper.get_inputs()[0]
    print(inp['disasm_file'])

    result, exit_code = sym_exec.run(disasm_file=inp['disasm_file'])
    helper.rm_tmp_files()

    if global_params.WEB:
        six.print_(json.dumps(result))

    return exit_code


def main():
    """Entrance for the analysis with input options"""
    # TODO: Implement -o switch.

    global args

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)

    # supported arguments refer to Oyente
    group.add_argument(
        "-s",
        "--source",
        type=str,
        help="local source file name. Solidity by default. Use -b to process evm instead. Use stdin to read from stdin.",
    )
    group.add_argument(
        "-ru",
        "--remoteURL",
        type=str,
        help="Get contract from remote URL. Solidity by default. Use -b to process evm instead.",
        dest="remote_URL",
    )

    parser.add_argument(
        "-cnames",
        "--target-contracts",
        type=str,
        nargs="+",
        help="The name of targeted contracts. If specified, only the specified contracts in the source code will be processed. By default, all contracts in Solidity code are processed.",
    )

    parser.add_argument(
        "--version", action="version", version="oyente version 0.2.7 - Commonwealth"
    )

    parser.add_argument(
        "-rmp", "--remap", help="Remap directory paths", action="store", type=str
    )
    parser.add_argument(
        "-t", "--timeout", help="Timeout for Z3 in ms.", action="store", type=int
    )
    parser.add_argument(
        "-gl",
        "--gaslimit",
        help="Limit Gas",
        action="store",
        dest="gas_limit",
        type=int,
    )
    parser.add_argument(
        "-rp",
        "--root-path",
        help="Root directory path used for the online version",
        action="store",
        dest="root_path",
        type=str,
    )
    parser.add_argument(
        "-ll",
        "--looplimit",
        help="Limit number of loops",
        action="store",
        dest="loop_limit",
        type=int,
    )
    parser.add_argument(
        "-dl",
        "--depthlimit",
        help="Limit DFS depth",
        action="store",
        dest="depth_limit",
        type=int,
    )
    parser.add_argument(
        "-ap",
        "--allow-paths",
        help="Allow a given path for imports",
        action="store",
        dest="allow_paths",
        type=str,
    )
    parser.add_argument(
        "-glt",
        "--global-timeout",
        help="Timeout for symbolic execution",
        action="store",
        dest="global_timeout",
        type=int,
    )

    parser.add_argument(
        "-e", "--evm", help="Do not remove the .evm file.", action="store_true"
    )
    parser.add_argument(
        "-w", "--web", help="Run Oyente for web service", action="store_true"
    )
    parser.add_argument(
        "-j", "--json", help="Redirect results to a json file.", action="store_true"
    )
    parser.add_argument(
        "-p", "--paths", help="Print path condition information.", action="store_true"
    )
    parser.add_argument(
        "-db", "--debug", help="Display debug information", action="store_true"
    )
    parser.add_argument(
        "-st", "--state", help="Get input state from state.json", action="store_true"
    )
    parser.add_argument(
        "-r", "--report", help="Create .report file.", action="store_true"
    )
    parser.add_argument(
        "-v", "--verbose", help="Verbose output, print everything.", action="store_true"
    )
    parser.add_argument(
        "-pl",
        "--parallel",
        help="Run Oyente in parallel. Note: The performance may depend on the contract",
        action="store_true",
    )
    parser.add_argument(
        "-b",
        "--bytecode",
        help="read bytecode in source instead of solidity file.",
        action="store_true",
    )
    parser.add_argument(
        "-a", "--assertion", help="Check assertion failures.", action="store_true"
    )
    parser.add_argument(
        "-sj",
        "--standard-json",
        help="Support Standard JSON input",
        action="store_true",
    )
    parser.add_argument(
        "-gb",
        "--globalblockchain",
        help="Integrate with the global ethereum blockchain",
        action="store_true",
    )
    parser.add_argument(
        "-ce",
        "--compilation-error",
        help="Display compilation errors",
        action="store_true",
    )
    parser.add_argument(
        "-gtc",
        "--generate-test-cases",
        help="Generate test cases each branch of symbolic execution tree",
        action="store_true",
    )
    parser.add_argument(
        "-sjo",
        "--standard-json-output",
        help="Support Standard JSON output",
        action="store_true",
    )

    args = parser.parse_args()

    if args.timeout:
        global_params.TIMEOUT = args.timeout

    logging.basicConfig()
    rootLogger = logging.getLogger(None)

    if args.verbose:
        rootLogger.setLevel(level=logging.DEBUG)
    else:
        rootLogger.setLevel(level=logging.INFO)

    global_params.PRINT_PATHS = 1 if args.paths else 0
    global_params.REPORT_MODE = 1 if args.report else 0

    global_params.STORE_RESULT = 1 if args.json else 0
    global_params.DEBUG_MODE = 1 if args.debug else 0
    global_params.GENERATE_TEST_CASES = 1 if args.generate_test_cases else 0
    global_params.PARALLEL = 1 if args.parallel else 0

    if args.target_contracts and args.bytecode:
        parser.error(
            'Targeted contracts cannot be specifed when the bytecode is provided (Instead of Solidity source code).'
        )
    global_params.TARGET_CONTRACTS = args.target_contracts

    # set limit to set execution bounds
    if args.depth_limit:
        global_params.DEPTH_LIMIT = args.depth_limit
    if args.gas_limit:
        global_params.GAS_LIMIT = args.gas_limit
    if args.loop_limit:
        global_params.LOOP_LIMIT = args.loop_limit
    else:
        if args.global_timeout:
            global_params.GLOBAL_TIMEOUT = args.global_timeout

    if not has_dependencies_installed():
        return

    # analyze bytecode
    exit_code = analyze_bytecode()

    exit(exit_code)


if __name__ == "__main__":
    main()
