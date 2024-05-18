/* Copyright (c) 2022-2023. The SWAT Team. All rights reserved.          */

/* This program is free software; you can redistribute it and/or modify it
 * under the terms of the license (GNU LGPL) which comes with this package. */
#include <simgrid/s4u.hpp>
namespace sg4 = simgrid::s4u;

sg4::NetZone*
no_gpu_no_nvme(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id);

sg4::NetZone*
no_gpu_nvme(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id);

sg4::NetZone*
gpu_no_nvme(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id);

sg4::NetZone*
gpu_nvme(const sg4::NetZone* parent_zone, const std::vector<unsigned long>& /*coord*/, unsigned long id);

sg4::Link* limiter(sg4::NetZone* zone, const std::vector<unsigned long>& /*coord*/, unsigned long id);