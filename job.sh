#!/bin/bash
#SBATCH --job-name=astralog
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:01:00
#SBATCH --output=%x-%j.out
#SBATCH --error=%x-%j.err

module load singularity

cd "$SLURM_SUBMIT_DIR"

singularity run \
        --bind "$SLURM_SUBMIT_DIR/out:/app/out" \
        astralog.sif