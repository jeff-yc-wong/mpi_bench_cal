/* Copyright (c) 2022-2023. The SWAT Team. All rights reserved.          */

/* This program is free software; you can redistribute it and/or modify it
 * under the terms of the license (GNU LGPL) which comes with this package. */

#include "node_config.hpp"
#include "summit_base.hpp"
#include <iostream>

static void add_gpus_to_cpu(sg4::NetZone* node_zone, const sg4::Host* cpu, unsigned int cpu_id)
{
  const sg4::Host* gpus[3];
  for (unsigned int g = 0; g < 3; g++) {
    std::string gpu_name = node_zone->get_name() + "-gpu-" + std::to_string(3 * cpu_id + g);
    gpus[g]              = node_zone->create_host(gpu_name, gpu_speed);

    // add direct CPU-GPU NV-links
    auto* nvlink = node_zone->create_link(std::string("nvlink-") + cpu->get_cname() + "-" + gpu_name,
                                          cpu_gpu_nvlink_bw)
                            ->set_latency(cpu_gpu_nvlink_lat); // nvlink latency not documented
    node_zone->add_route(cpu, gpus[g], {nvlink});
  }

  // add direct GPU-GPU NV-links
  //  ------------------------------
  //  |                            |
  //  -- gpu-0  -- gpu-1 -- gpu-2 --
  for (unsigned int g = 0; g < 3; g++) {
    auto* nvlink =
        node_zone
             ->create_link(std::string("nvlink-") + gpus[g]->get_cname() + "-" + gpus[(g + 1) % 3]->get_cname(),
                           gpu_gpu_nvlink_bw)
              ->set_latency(gpu_gpu_nvlink_lat); // nvlink latency not documented
    node_zone->add_route(gpus[g], gpus[(g + 1) % 3], {nvlink});
  }
}

static void add_NVMe_to_cpus(const std::string& node_name, sg4::Host** cpus)
{
  /* create the NVMe as a disk attached to one CPU */
  auto* nvme = cpus[0]->create_disk(node_name + "-NVMe", nvme_read_bw, nvme_write_bw);
  /* then have the other CPU access it too */
  /* NOTE: PCIe link to NVMe is not modeled here. This is not compatible with how local disk are declared in SimGrid */
  cpus[1]->add_disk(nvme);
}

static simgrid::kernel::routing::NetPoint* add_cpus_and_nic(sg4::NetZone* node_zone, bool with_gpus, bool with_nvme)
{
  const std::string node_name = node_zone->get_cname();
  // use the NIC as a gateway for each node
  auto* nic = node_zone->create_router(node_name + "-nic");

  sg4::Host* cpus[2];
  for (unsigned int c = 0; c < 2; c++) {
    std::string cpu_name = node_name + "-cpu-" + std::to_string(c);
    cpus[c]              = node_zone->create_host(cpu_name, cpu_speed)->set_core_count(cpu_core_count);

    if (with_gpus)
      add_gpus_to_cpu(node_zone, cpus[c], c);

    // add PCIe link from CPU to the NIC
    auto* pcilink = node_zone->create_link(std::string("pcie-link-") + cpu_name, pcie_bw)
                             ->set_latency(pcie_lat); // PCIe link latency not documented
    node_zone->add_route(cpus[c]->get_netpoint(), nic, nullptr, nullptr, {sg4::LinkInRoute(pcilink)});
  }

  // Add X-bus between the two CPUs
  auto* xbus = node_zone->create_link(std::string("bus-") + node_name, xbus_bw)
                   ->set_latency(xbus_lat); // X-bus latency not documented

  node_zone->add_route(cpus[0], cpus[1], {xbus});

  if (with_nvme)
    add_NVMe_to_cpus(node_name, cpus);

  return nic;
}

sg4::NetZone* create_node(const sg4::NetZone* parent_zone, unsigned long id, bool with_gpus, bool with_nvme)
{
  auto* node_zone = sg4::create_full_zone("node-" + std::to_string(id))->set_parent(parent_zone);
  auto* nic       = add_cpus_and_nic(node_zone, with_gpus, with_nvme);
  /* the NIC is the gateway for this node */
  node_zone->set_gateway(nic);
  node_zone->seal();

  return node_zone;
}

sg4::NetZone* create_simple_node(const sg4::NetZone* parent_zone, unsigned long id)
{
  auto* node_zone = sg4::create_full_zone("node-" + std::to_string(id))->set_parent(parent_zone);

  const std::string node_name = node_zone->get_cname();

  std::string cpu_name = node_name + "-cpu-0";

  node_zone->create_host(cpu_name, cpu_speed)->set_core_count(cpu_core_count);
  node_zone->seal();

  return node_zone;
}

sg4::NetZone* simple_node(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id)
{
  return create_simple_node(parent_zone, id);
}

sg4::NetZone* no_gpu_no_nvme(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id)
{
  return create_node(parent_zone, id, false, false);
}

sg4::NetZone* no_gpu_nvme(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id)
{
  return create_node(parent_zone, id, false, true);
}

sg4::NetZone* gpu_no_nvme(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id)
{
  return create_node(parent_zone, id, true, false);
}

sg4::NetZone* gpu_nvme(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id)
{
  return create_node(parent_zone, id, true, true);
}

sg4::Link* limiter(sg4::NetZone* zone, const std::vector<unsigned long>& /*coord*/, unsigned long id)
{
  return zone->create_link("limiter-" + std::to_string(id), limiter_bw);
}
