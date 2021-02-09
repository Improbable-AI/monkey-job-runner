#!/usr/bin/env python3
import argparse

from utils import aws_cred_file_environment

parser = argparse.ArgumentParser()

parser.add_argument('file')
parser.add_argument('-s', '--secret', action="store_true")
parser.add_argument('-k', '--key', action="store_true")
args = parser.parse_args()

if not args.secret and not args.key:
    raise ValueError("Did not input secret or key")

if args.secret and args.key:
    raise ValueError("Please only put in one secret or key")

parsed = aws_cred_file_environment(args.file)
if args.secret:
    print(parsed["AWS_SECRET_ACCESS_KEY"])

if args.key:
    print(parsed["AWS_ACCESS_KEY_ID"])
