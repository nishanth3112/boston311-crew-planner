Intake eval on `data/processed/intake_test_set.csv`, model `openai/gpt-oss-120b`

| path | messages | errors | type correct | department correct | queue correct | split correct | follow-up precision | follow-up recall | out of scope correct | tool calls / msg | LLM calls / msg | uncached tokens / msg | fallbacks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pipeline | 45 | 0 | 31/41 | 34/41 | 33/41 | 4/6 | 2/2 | 2/8 | 2/3 | 0.0 | 1.0 | 614.3 | 0 |
| agent | 45 | 0 | 33/41 | 37/41 | 35/41 | 6/6 | 0/0 | 0/8 | 3/3 | 1.4 | 2.4 | 1303.9 | 12 |

Per message

| id | path | expected | got |
|---|---|---|---|
| T01 | pipeline | Request for Pothole Repair | Request for Pothole Repair |
| T02 | pipeline | Missed Trash/Recycling/Yard Waste/Bulk Item | Missed Trash/Recycling/Yard Waste/Bulk Item |
| T03 | pipeline | Street Light Outages | Street Light Outages |
| T04 | pipeline | PWD Graffiti | Graffiti Removal |
| T05 | pipeline | Parking Enforcement | Parking Enforcement |
| T06 | pipeline | Parking Enforcement | Parking Enforcement |
| T07 | pipeline | Traffic Signal Inspection or Traffic Signal Repair | Traffic Signal Inspection |
| T08 | pipeline | Tree Emergencies or Tree Maintenance Requests | Tree Emergencies |
| T09 | pipeline | Equipment Repair | Equipment Repair |
| T10 | pipeline | Rodent Activity | Rodent Activity |
| T11 | pipeline | Heat - Excessive  Insufficient | Heat - Excessive  Insufficient |
| T12 | pipeline | Sidewalk Repair (Make Safe) | Sidewalk Repair (Make Safe) |
| T13 | pipeline | Illegal Dumping | Illegal Dumping |
| T14 | pipeline | Schedule a Bulk Item Pickup | Schedule a Bulk Item Pickup |
| T15 | pipeline | Requests for Street Cleaning | Requests for Street Cleaning |
| T16 | pipeline | Sign Repair | Missing Sign |
| T17 | pipeline | Parking Enforcement | Parking Enforcement |
| T18 | pipeline | Empty Litter Basket | Empty Litter Basket |
| T19 | pipeline | Pick up Dead Animal | Pick up Dead Animal |
| T20 | pipeline | Work w/out Permit | Work w/out Permit |
| T21 | pipeline | Ground Maintenance | Ground Maintenance |
| T22 | pipeline | Tree Maintenance Requests | Tree Maintenance Requests |
| T23 | pipeline | Parking Enforcement | Parking Meter Repairs |
| T24 | pipeline | Unsanitary Conditions - Establishment | Unsanitary Conditions - Food |
| T25 | pipeline | Pavement Marking Inspection or Pavement Marking Maintenance | Pavement Marking Maintenance |
| T26 | pipeline | Street Light Outages | Street Light Outages |
| T27 | pipeline | Abandoned Vehicles | Abandoned Vehicles |
| T28 | pipeline | Requests for Street Cleaning | (follow-up) |
| T29 | pipeline | Sidewalk Repair (Make Safe) | Sidewalk Repair (Make Safe) |
| T30 | pipeline | Tree Maintenance Requests | Tree Emergencies |
| T31 | pipeline | Rodent Activity | (follow-up) |
| T32 | pipeline | Sign Repair | Sign Repair |
| T33 | pipeline | Ground Maintenance or Illegal Dumping or Empty Litter Basket | Construction Debris |
| T34 | pipeline | Missed Trash/Recycling/Yard Waste/Bulk Item / Pick up Dead Animal or Rodent Activity | Missed Trash/Recycling/Yard Waste/Bulk Item |
| T35 | pipeline | Request for Pothole Repair / Street Light Outages | Request for Pothole Repair / Street Light Outages |
| T36 | pipeline | Illegal Dumping / Equipment Repair | Parks General Request / Equipment Repair |
| T37 | pipeline | Mice Infestation - Residential / Unsatisfactory Utilities - Electrical  Plumbing / Parking Enforcement | Mice Infestation - Residential |
| T38 | pipeline | PWD Graffiti / Traffic Signal Inspection or Traffic Signal Repair | PWD Graffiti / Traffic Signal Repair |
| T39 | pipeline | Tree Emergencies / Sign Repair | Tree Emergencies / Sign Repair |
| T40 | pipeline | (none) | (none) |
| T41 | pipeline | (none) | Major System Failure |
| T42 | pipeline | (none) | (none) |
| T43 | pipeline | Request for Pothole Repair | Request for Pothole Repair |
| T44 | pipeline | Request for Pothole Repair | (none) |
| T45 | pipeline | Street Light Outages | (none) |
| T01 | agent | Request for Pothole Repair | Request for Pothole Repair |
| T02 | agent | Missed Trash/Recycling/Yard Waste/Bulk Item | Missed Trash/Recycling/Yard Waste/Bulk Item |
| T03 | agent | Street Light Outages | Street Light Outages |
| T04 | agent | PWD Graffiti | PWD Graffiti |
| T05 | agent | Parking Enforcement | Parking Enforcement |
| T06 | agent | Parking Enforcement | Parking on Front/Back Yards (Illegal Parking) |
| T07 | agent | Traffic Signal Inspection or Traffic Signal Repair | Traffic Signal Repair |
| T08 | agent | Tree Emergencies or Tree Maintenance Requests | Tree Emergencies |
| T09 | agent | Equipment Repair | Equipment Repair |
| T10 | agent | Rodent Activity | Rodent Activity |
| T11 | agent | Heat - Excessive  Insufficient | Heat - Excessive  Insufficient |
| T12 | agent | Sidewalk Repair (Make Safe) | Sidewalk Repair (Make Safe) |
| T13 | agent | Illegal Dumping | Illegal Dumping |
| T14 | agent | Schedule a Bulk Item Pickup | Schedule a Bulk Item Pickup |
| T15 | agent | Requests for Street Cleaning | Requests for Street Cleaning |
| T16 | agent | Sign Repair | Missing Sign |
| T17 | agent | Parking Enforcement | Parking Enforcement |
| T18 | agent | Empty Litter Basket | Empty Litter Basket |
| T19 | agent | Pick up Dead Animal | Pick up Dead Animal |
| T20 | agent | Work w/out Permit | Work w/out Permit |
| T21 | agent | Ground Maintenance | Ground Maintenance |
| T22 | agent | Tree Maintenance Requests | Tree Maintenance Requests |
| T23 | agent | Parking Enforcement | Parking Meter Repairs |
| T24 | agent | Unsanitary Conditions - Establishment | Illegal Dumping |
| T25 | agent | Pavement Marking Inspection or Pavement Marking Maintenance | Pavement Marking Maintenance |
| T26 | agent | Street Light Outages | Street Light Outages |
| T27 | agent | Abandoned Vehicles | Parking Enforcement |
| T28 | agent | Requests for Street Cleaning | Trash on Vacant Lot |
| T29 | agent | Sidewalk Repair (Make Safe) | Sidewalk Repair |
| T30 | agent | Tree Maintenance Requests | Tree Maintenance Requests |
| T31 | agent | Rodent Activity | Rodent Activity |
| T32 | agent | Sign Repair | Sign Repair |
| T33 | agent | Ground Maintenance or Illegal Dumping or Empty Litter Basket | Trash on Vacant Lot |
| T34 | agent | Missed Trash/Recycling/Yard Waste/Bulk Item / Pick up Dead Animal or Rodent Activity | Missed Trash/Recycling/Yard Waste/Bulk Item / Rodent Activity |
| T35 | agent | Request for Pothole Repair / Street Light Outages | Request for Pothole Repair / Street Light Outages |
| T36 | agent | Illegal Dumping / Equipment Repair | Illegal Dumping / Equipment Repair |
| T37 | agent | Mice Infestation - Residential / Unsatisfactory Utilities - Electrical  Plumbing / Parking Enforcement | Pest Infestation - Residential / Heat - Excessive  Insufficient / Parking Enforcement |
| T38 | agent | PWD Graffiti / Traffic Signal Inspection or Traffic Signal Repair | PWD Graffiti / Traffic Signal Repair |
| T39 | agent | Tree Emergencies / Sign Repair | Tree Emergencies / Sign Repair |
| T40 | agent | (none) | (none) |
| T41 | agent | (none) | (none) |
| T42 | agent | (none) | (none) |
| T43 | agent | Request for Pothole Repair | Request for Pothole Repair |
| T44 | agent | Request for Pothole Repair | (none) |
| T45 | agent | Street Light Outages | (none) |
