/* Copyright (c) 2022-2023. The SWAT Team. All rights reserved.          */

/* This program is free software; you can redistribute it and/or modify it
 * under the terms of the license (GNU LGPL) which comes with this package. */

#include <simgrid/s4u.hpp>
namespace sg4 = simgrid::s4u;

XBT_LOG_NEW_DEFAULT_CATEGORY(summit, "SWAT description of Summit (ORNL)");

static void dump_node(const std::string& name)
{
  auto* node_zone = sg4::Engine::get_instance()->netzone_by_name_or_null(name);
  xbt_assert(node_zone, "Node '%s' does not exist", name.c_str());
  auto hosts = node_zone->get_all_hosts();
  for (auto const* h : hosts) {
    XBT_INFO("Host '%s': speed=%.0g, core count=%d", h->get_cname(), h->get_speed(), h->get_core_count());
    for (auto const* d : h->get_disks())
      XBT_INFO("    %s: read: %.0f write: %.0f", d->get_cname(), d->get_read_bandwidth(), d->get_write_bandwidth());
    for (auto const* h2 : hosts) {
      if (h2 == h)
        continue;
      std::vector<sg4::Link*> route;
      double latency = 0;
      h->route_to(h2, route, &latency);
      if (route.empty())
        continue;
      XBT_INFO("  [%s -> %s]: ", h->get_cname(), h2->get_cname());
      for (auto const& link : route)
        XBT_INFO("    Link '%s': latency = %g, bandwidth = %g", link->get_cname(), link->get_latency(),
                 link->get_bandwidth());
    }
  }
}

int main(int argc, char* argv[])
{
  sg4::Engine e(&argc, argv);

  e.load_platform(argv[1]);

  XBT_INFO("Total number of nodes: %lu", e.get_netzone_root()->get_children().size());
  dump_node("node-0");

  e.run();
  return 0;
}
