# DiRAC one line benchmark


check_os(){
  # Check that this is running on a supported OS

  if [ "$(uname)" != "Linux" ]; then
  echo "Cannot run the benchmark on anything but a Linux OS"
  exit 1
fi
}


ensure_conda_exists(){
  # Install conda if it does not exist

  if ! command -v conda &> /dev/null ; then
    install_conda
  fi
}


install_conda () {
  # Install conda using miniforge

  arch=$(uname -m)

  if [ "$arch" == "arm64" ]; then
    curl -L "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh" > miniconda_installer.sh
  elif [ "$arch" == "x86_64" ]; then
    curl -L "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh" > miniconda_installer.sh
  else
    echo "Cannot install miniconda for arch = $arch"
    exit 1
  fi

  if [ ! -d "$PWD/miniforge" ]; then
    bash miniconda_installer.sh -b -p "$PWD/miniforge"
  fi

  eval "$("$PWD"/miniforge/bin/conda shell.bash hook)"
  rm -rf miniconda_installer.sh
}


install_python_and_git(){
  # Install a recent version of python and git using conda binaries

  conda install git python=3.9 --yes -q
}


install_spack(){
  # Install spack to build the benchmark applications

  if [ ! -d "spack" ]; then
    git clone -c feature.manyFiles=true https://github.com/spack/spack.git -q
  fi

  source spack/share/spack/setup-env.sh
}


run_gromacs_benchmark(){
  # Download the data and run a benchmark for GROMACS

  conda install scipy --yes

  mkdir -p gromacs
  cd gromacs || return

  # TODO: Change branch
  prefix="https://raw.githubusercontent.com/t-young31/excalibur-tests/olb/one-line-benchmark/gromacs"
  curl -L "$prefix/benchmark.tpr" > benchmark.tpr
  curl -L "$prefix/benchmark.py" > benchmark.py
  python benchmark.py
}


check_os
ensure_conda_exists
install_python_and_git
install_spack

run_gromacs_benchmark
