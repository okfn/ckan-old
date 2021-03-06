
+--------------------------------+-------------------------------------------------------------------+
| Model Resource                 | Location                                                          |
+================================+===================================================================+
| Package Register               | ``/rest/package``                                                 |
+--------------------------------+-------------------------------------------------------------------+
| Package Entity                 | ``/rest/package/PACKAGE-REF``                                     |
+--------------------------------+-------------------------------------------------------------------+
| Group Register                 | ``/rest/group``                                                   |
+--------------------------------+-------------------------------------------------------------------+
| Group Entity                   | ``/rest/group/GROUP-NAME``                                        |
+--------------------------------+-------------------------------------------------------------------+
| Tag Register                   | ``/rest/tag``                                                     |
+--------------------------------+-------------------------------------------------------------------+
| Tag Entity                     | ``/rest/tag/TAG-NAME``                                            |
+--------------------------------+-------------------------------------------------------------------+
| Rating Register                | ``/rest/rating``                                                  |
+--------------------------------+-------------------------------------------------------------------+
| Rating Entity                  | ``/rest/rating/PACKAGE-REF``                                      |
+--------------------------------+-------------------------------------------------------------------+
| Package Relationships Register | ``/rest/package/PACKAGE-REF/relationships``                       |
+--------------------------------+-------------------------------------------------------------------+
| Package Relationships Register | ``/rest/package/PACKAGE-REF/relationships/PACKAGE-REF``           |
+--------------------------------+-------------------------------------------------------------------+
| Package Relationship Entity    | ``/rest/package/PACKAGE-REF/RELATIONSHIP-TYPE/PACKAGE-REF``       |
+--------------------------------+-------------------------------------------------------------------+
| Revision Register              | ``/rest/revision``                                                |
+--------------------------------+-------------------------------------------------------------------+
| Revision Entity                | ``/rest/revision/REVISION-ID``                                    |
+--------------------------------+-------------------------------------------------------------------+
| License List                   | ``/rest/licenses``                                                |
+--------------------------------+-------------------------------------------------------------------+
| Harvest Source Entity          | ``/rest/harvestsource/HARVESTSOURCE-ID``                          |
+--------------------------------+-------------------------------------------------------------------+
| Publisher's Harvest Source     | ``/rest/harvestsource/publisher/PUBLISHER-REF``                   |
| Register                       |                                                                   |
+--------------------------------+-------------------------------------------------------------------+
| Harvesting Job Register        | ``/rest/harvestingjob``                                           |
+--------------------------------+-------------------------------------------------------------------+
| Harvesting Job Queue           | ``/rest/harvestingjob/status/new``                                |
+--------------------------------+-------------------------------------------------------------------+
| Harvesting Job Errors          | ``/rest/harvestingjob/status/error``                              |
+--------------------------------+-------------------------------------------------------------------+
| Harvesting Job Entity          | ``/rest/harvestingjob/HARVESTINGJOB-ID``                          |
+--------------------------------+-------------------------------------------------------------------+

Possible values for PACKAGE-REF are the package id, or the current package name.

Possible values for RELATIONSHIP-TYPE are described in the Relationship-Type data format.


