#Copyright (c) 2022-2023. The SWAT Team. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the license (GNU LGPL) which comes with this package.
import json
import sys
import subprocess
from pathlib import Path

SIMGRID_INSTALL_PATH = "/home/wongy/local" #NOTE: change this accordingly

f_node = open(sys.argv[1])
node = json.load(f_node)

# get path of this file
path = Path(__file__).parent.absolute()

# check if lib folder exists
lib_dir = path / "lib"

if not lib_dir.exists():
    lib_dir.mkdir(parent=True)

with open(path / 'src/node_config.hpp', 'w') as f:
      f.write("constexpr int cpu_core_count = " + str(node["cpu_core_count"]) + ";\n")
      f.write("constexpr const char* cpu_speed = \"" + node["cpu_speed"] + "\";\n")
      f.write("constexpr const char* gpu_speed = \"" + node["gpu_speed"] + "\";\n\n")
      f.write("constexpr const char* pcie_bw = \"" + node["pcie_bw"] + "\";\n")
      f.write("constexpr const char* pcie_lat = \"" + node["pcie_lat"] + "\";\n\n")
      f.write("constexpr const char* xbus_bw = \"" + node["xbus_bw"] + "\";\n")
      f.write("constexpr const char* xbus_lat = \"" + node["xbus_lat"] + "\";\n\n")
      f.write("constexpr const char* cpu_gpu_nvlink_bw = \"" + node["cpu_gpu_nvlink_bw"] + "\";\n")
      f.write("constexpr const char* cpu_gpu_nvlink_lat = \"" + node["cpu_gpu_nvlink_lat"] + "\";\n")
      f.write("constexpr const char* gpu_gpu_nvlink_bw = \"" + node["gpu_gpu_nvlink_bw"] + "\";\n")
      f.write("constexpr const char* gpu_gpu_nvlink_lat = \"" + node["gpu_gpu_nvlink_lat"] + "\";\n\n")
      f.write("constexpr const char* nvme_read_bw = \"" + node["nvme_read_bw"] + "\";\n")
      f.write("constexpr const char* nvme_write_bw = \"" + node["nvme_write_bw"] + "\";\n\n")
      f.write("constexpr const char* limiter_bw = \"" + node["limiter_bw"] + "\";\n")

f_topo = open(sys.argv[2])
topo = json.load(f_topo)

with open('tmp.cpp', 'w') as f:
      f.write("#include \"summit_base.hpp\"\n")
      f.write("extern \"C\" void load_platform(const sg4::Engine& e);\n")
      f.write("void load_platform(const sg4::Engine&)\n")
      f.write("{\n")
      f.write("sg4::create_fatTree_zone(\"" + topo["name"] +"\", nullptr, {" +
              str(topo["Fat-Tree_parameters"]["levels"]) + ", " + topo["Fat-Tree_parameters"]["up_links"] + ", " +
              topo["Fat-Tree_parameters"]["down_links"] + ", " + topo["Fat-Tree_parameters"]["links_number"] +
              "}, {" + topo["node_generator_cb"] + ", {}, " + topo["limiter_cb"] + "}, " +
              str(topo["bandwidth"]) + ", " + str(topo["latency"]) +
              ", sg4::Link::SharingPolicy::" + topo["sharing_policy"] +")->seal();\n")
      f.write("}\n")

base   = subprocess.run(['g++', '-v', '--std=c++17', '-I'+ SIMGRID_INSTALL_PATH +'/include', '-L'+ SIMGRID_INSTALL_PATH +
                        '/lib64/', '-lsimgrid', '-fPIC', '-g', '-O2', '-Wall', '-Wextra', '-c', path / 'src/summit_base.cpp', '-o',
                        path / 'lib/summit_base.o'])
if base.returncode != 0:
      sys.stderr.write("Compilation of summit_base.cpp failed\n")
      sys.exit(1)

compil = subprocess.run(['g++', '--std=c++17', '-v', '-I'+ SIMGRID_INSTALL_PATH +'/include', '-I' + (str(path / 'src')),
                         '-L'+ SIMGRID_INSTALL_PATH + '/lib64/', '-lsimgrid', '-fPIC', '-g', '-O2', '-Wall', '-Wextra',
                         '-c', 'tmp.cpp', '-o', 'tmp.o'])

if compil.returncode != 0:
      sys.stderr.write("Compilation of tmp.cppfailed\n")
      sys.exit(1)

link   = subprocess.run(['g++','-v', '--std=c++17', '-shared', '-I'+ SIMGRID_INSTALL_PATH +'/include', '-L'+SIMGRID_INSTALL_PATH + '/lib64', '-lsimgrid', 'tmp.o', '-o', topo["name"] + ".so",
                        path / "lib/summit_base.o"])
if link.returncode != 0:
      sys.stderr.write("Linking failed\n")
      sys.exit(1)

clean  = subprocess.run(['rm', '-f', 'tmp.cpp', 'tmp.o'])

base
compil
link
# clean
