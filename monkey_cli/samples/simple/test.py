import argparse
import os

print("Hello From python script")
parser = argparse.ArgumentParser(description='Simple parser')

parser.add_argument('-i','--input-dir', default=os.environ.get('INPUT_DIR'))
parser.add_argument('-o','--output-dir', default=os.environ.get('OUTPUT_DIR'))

args = parser.parse_args()

if not args.input_dir:
  raise ValueError("Did not input --input-dir folder (INPUT_DIR)")

if not args.output_dir:
  raise ValueError("Did not input --output-dir folder (OUTPUT_DIR)")


input_dir = args.input_dir
output_dir = args.output_dir
test_env = os.environ.get("TEST_ENV")
with open(os.path.join(output_dir, "testfile.txt"), 'w') as f:
  print("Opened output file correctly. TEST_ENV={}".format(test_env))
  f.write("Test file success")

print("Written to output directory")