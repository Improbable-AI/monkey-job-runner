#!/usr/bin/env python
import os

from monkeycli import MonkeyCLI

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/home/ubuntu/results")
base_command = f"docker kill workflow_gabe; \
        docker pull gmargo11/dynamicloco:latest; \
        nice -n 19 docker run -t --rm -w=/workspace/locomotion/mini_cheetah/pycheetah/cheetah_gym \
        --name='workflow_gabe' \
        --env-file='./env_file.env' \
        --volume='{OUTPUT_DIR}:/workspace/locomotion/mini_cheetah/pycheetah/cheetah_gym/data'     \
        --privileged --runtime=nvidia --net=host --entrypoint=python3 gmargo11/dynamicloco:latest "

flat_policy = "learn_gp_ppo.py \
        --env_name CheetahMPCEnvICRAFlat-v0 \
        --save_dir ./data/icra_runs/train/flat_policy/dt10ms \
        --env_params_file Full-Frame-Config-Half-Width-control_dt_10ms \
        --dataset_path \
        ./dataset/gap_world_lowres_upto16cm_sparse/train \
        --ent_coef 0.0 \
        --episode_steps=1300 \
        --rew_discount=0.99 \
        --log_interval=10 \
        --eval_interval=10 \
        --max_steps=1000000000 \
        --max_decay_steps=1000000000 \
        --no_linear_decay_clip_range \
        --no_linear_decay_lr \
        --ent_coef=0.0 \
        --batch_size=128 \
        --max_grad_norm=10  \
        --num_envs=32 \
        --num_stack=1 \
        --seed=1"

flat_policy2 = "learn_gp_ppo.py \
        --env_name CheetahMPCEnvICRAFlat-v0 \
        --save_dir ./data/icra_runs/train/flat_policy/dt20ms \
        --env_params_file Full-Frame-Config-Half-Width-control_dt_20ms \
        --dataset_path ./dataset/gap_world_lowres_upto16cm_sparse/train \
        --ent_coef 0.0 \
        --episode_steps=650 \
        --rew_discount=0.99 \
        --log_interval=10 \
        --eval_interval=10 \
        --max_steps=1000000000 \
        --max_decay_steps=1000000000 \
        --no_linear_decay_clip_range \
        --no_linear_decay_lr \
        --ent_coef=0.0 \
        --batch_size=128 \
        --max_grad_norm=10  \
        --num_envs=32 \
        --num_stack=1 \
        --seed=1"

# Gait ablations
gait_1 = "learn_gp_ppo.py \
        --env_name=CheetahMPCEnvICRA-v0 \
        --episode_steps=100 \
        --rew_discount=0.99 \
        --log_interval=10 \
        --eval_interval=10 \
        --max_steps=1000000000 \
        --max_decay_steps=1000000000 \
        --no_linear_decay_clip_range \
        --no_linear_decay_lr \
        --ent_coef=0.0 \
        --batch_size=128 \
        --max_grad_norm=10 \
        --save_dir=./data/icra_runs/train/long_body_centered_hmap/no_foot_displacements  \
        --num_envs=32 \
        --num_stack=1 \
        --seed=1 \
        --dataset_path ./dataset/gap_world_lowres_upto16cm_sparse/train \
        --env_params_file No-Foot-Displacements-FFCHW"

gait_2 = "learn_gp_ppo.py \
        --env_name=CheetahMPCEnvICRA-v0 \
        --episode_steps=100 \
        --rew_discount=0.99 \
        --log_interval=10 \
        --eval_interval=10 \
        --max_steps=1000000000 \
        --max_decay_steps=1000000000 \
        --no_linear_decay_clip_range \
        --no_linear_decay_lr \
        --ent_coef=0.0 \
        --batch_size=128 \
        --max_grad_norm=10 \
        --save_dir=./data/icra_runs/train/long_body_centered_hmap/no_foot_displacements  \
        --num_envs=32 \
        --num_stack=1 \
        --seed=1 \
        --dataset_path ./dataset/gap_world_lowres_upto16cm_sparse/train \
        --env_params_file No-Foot-Displacements-RPY-FFCHW"

gait_3 = "learn_gp_ppo.py \
        --env_name=CheetahMPCEnvICRA-v0 \
        --episode_steps=100 \
        --rew_discount=0.99 \
        --log_interval=10 \
        --eval_interval=10 \
        --max_steps=1000000000 \
        --max_decay_steps=1000000000 \
        --no_linear_decay_clip_range \
        --no_linear_decay_lr \
        --ent_coef=0.0 \
        --batch_size=128 \
        --max_grad_norm=10 \
        --save_dir=./data/icra_runs/train/long_body_centered_hmap/no_foot_displacements  \
        --num_envs=32 \
        --num_stack=1 \
        --seed=1 \
        --dataset_path ./dataset/gap_world_lowres_upto16cm_sparse/train \
        --env_params_file No-Gait-Adaptation-FFCHW"

print("\n\n----------------------------------------------\n")
monkey = MonkeyCLI()
print(base_command + flat_policy)
print("\n\n----------------------------------------------\n")
print(base_command + flat_policy)
print("\n\n----------------------------------------------\n")
print(base_command + flat_policy2)
print("\n\n----------------------------------------------\n")
print(base_command + gait_1)
print("\n\n----------------------------------------------\n")
print(base_command + gait_2)
print("\n\n----------------------------------------------\n")
print(base_command + gait_3)
print("\n\n----------------------------------------------\n")
#monkey.run(base_command + flat_policy)
#monkey.run(base_command + flat_policy2)
#monkey.run(base_command + gait_1)
#monkey.run(base_command + gait_2)
#monkey.run(base_command + gait_3)
