#!/bin/bash
#SBATCH --job-name=astralog
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:02:00
#SBATCH --output=%x-%j.out
#SBATCH --error=%x-%j.err

module load singularity

mkdir -p "$TMPDIR/out"
cd "$SLURM_SUBMIT_DIR"

export ASTRALOG_NUM_THREADS=2

singularity run \
        --bind "$TMPDIR/out:/app/out" \
        astralog.sif \
        --reading-mode file \
        --batch-mode count \
        --limit 100 \
        --readings-file res/readings_alpha_large.csv \
        --sensors-file res/sensors_alpha.yaml \
        --rules-file res/rules_alpha.json \
        --output-dir out/raw \
        --alarms-output-file out/alarms.txt \
        --valid-output-file out/valid.txt \
        --duration 30

cp "$TMPDIR/out/alarms.txt" "$SLURM_SUBMIT_DIR/${SLURM_JOB_ID}-alarms.txt"
cp "$TMPDIR/out/valid.txt" "$SLURM_SUBMIT_DIR/${SLURM_JOB_ID}-valid.txt"