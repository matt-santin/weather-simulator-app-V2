"""The numbers the sky class turns on, and where each one comes from.

Values only. The decision tree that reads them belongs to step 3; what matters
here is that every threshold is written once, with its provenance attached, so
that changing one is a deliberate act rather than an edit in passing.
"""

from __future__ import annotations

# The wet gate. A day below this is not a precipitation day, whatever fell.
# Conventional for daily totals, and shared by the snow and rain rules so that
# the two partition the same set of days rather than overlap.
PRECIPITATION_MM = 1.0

# Snow, among wet days: below this daily mean temperature, the precipitation is
# shown as snow.
#
# Calibrated by script 21 over 35 winters at Strasbourg and Briancon, against
# the snow depth the reanalyses actually record — not against weather_code,
# which is the daily maximum of 24 hourly codes and therefore fires on a single
# snowy hour. That inflates snow by 16 points at Strasbourg and saturates
# outright at Briancon, where 999 wet days in 1000 carry a snow code.
#
# At 1.5 degrees: 90% of winter days right at Strasbourg, 82% at Briancon. No
# single value suits both. Above 1300 m snow settles even on days averaging well
# over 2 degrees — it falls at night, or higher up — and a daily mean cannot
# carry that. The rule under-calls snow in the mountains by construction.
#
# Provisional in the same sense as the cloud thresholds below: two sites and one
# season are a thin basis, and the design document says as much of its own
# measurements.
SNOW_TEMPERATURE_C = 1.5

# Cloud cover, among dry days — the wet ones are already taken by the two rules
# above, so these two thresholds partition those and nothing else.
#
# Confirmed at step 3, not merely carried over. They were provisional, and the
# obvious yardsticks for settling them both turned out to be traps.
# sunshine_duration overstates real sunshine by a third to a factor of two, the
# error growing with cloudiness; weather_code is the daily maximum of 24 hourly
# codes, calls half of Marseille's dry days overcast, and is circular anyway —
# a deterministic function of cloud cover itself.
#
# What settles them is the light that actually reaches the ground, from
# shortwave radiation over a clear-sky estimate. Script scripts/sky_thresholds/
# measures, over ten sites, that the three classes receive about 90 %, 80 % and
# 60 % of what a clear sky would give. Three clear steps, ordered the same way
# everywhere. No candidate pair did better: raising the overcast bar lowers the
# median but widens the spread by as much.
#
# Where "cloudy" ends and "overcast" begins remains a convention of language
# over a continuum. Measurement cannot place that line; it can only say what
# falls either side of it, which is what these figures do.
OVERCAST_PERCENT = 70.0
CLOUDY_PERCENT = 30.0

# The temperature colour scale: eight boundaries, nine bands.
#
# **Absolute, not an anomaly.** A band depends on the temperature and on nothing
# else — not on the date, not on the place. January is cold and July is warm, and
# the scale says so, which is what the public weather maps do.
#
# **Placed on what France actually recorded**, by scripts/temperature_scale/:
# twelve towns, one per French climate, 1981-2010, ERA5-Land — 131 484 days. The
# reference period is the WMO normal, and it is deliberately a cold one for a
# site that shows the future: at Paris, days at or above 30 °C run to 4.9 a year
# over 1981-2010 and to 21 over 2036-2050 in the climate model. The scale reddens
# as the century advances because the reference does not move.
#
# **The source is the reanalysis, not the record books.** A grid cell smooths
# extremes: no French cell of these thirty years reaches 40 °C, where station
# records do. Boundaries taken from an almanac would be colours the page could
# not display. The top band is therefore the one the reference climate never
# reaches and the simulated future does.
#
# **Nine bands, at five degrees.** Measured on the same data, over a 47-day
# search — the length of a typical one — a step of 10 °C shows 1.9 to 2.8 distinct
# colours and the strip reads as one flat wash; a step of 5 °C shows 2.7 to 4.0.
# Nine is also what a palette can name: dark blue, light blue, light green,
# yellow, orange, light red, dark red, dark violet, light violet. A scale whose
# steps cannot be named is a gradient, and a gradient claims a precision daily
# aggregates do not have.
#
# **Where the ladder starts is what keeps the colours honest.** Running 5 to 40
# rather than 0 to 35 puts each colour where a French reader expects it — yellow
# on 15-20, orange on 20-25, red from 25 — and leaves the top band, which the
# reference climate never reaches, to the heat the simulated future brings. The
# price is a coarse cold end: everything under 5 °C is one colour, which is 7 %
# of French maxima and 28 % of minima.
#
# The bands are a display convention over a continuum, exactly as "cloudy" and
# "overcast" are. Measurement says what falls either side of a line; it cannot
# say where to draw it.
TEMPERATURE_BAND_STEP_C = 5.0
TEMPERATURE_BAND_EDGES = tuple(5.0 + TEMPERATURE_BAND_STEP_C * step for step in range(8))

# Humid heat: two levels on the daily mean wet-bulb temperature, in degrees
# Celsius. Settled by the project owner on 2026-09-07, on the measurements below.
#
# **They read a mean, and that is what fixes their values.** Only the daily mean
# wet bulb is reconstructible from daily aggregates — the maximum costs ten times
# the error — and a mean sits 1.4 to 2.5 °C under the maximum of the same day. A
# number borrowed from the literature, which mostly speaks of peaks, therefore
# means something else once written here, and each of these was placed by
# measuring the correspondence rather than by transcription.
#
# **26 marks the first level.** Measured over ERA5 2015-2024, eight sites, a
# daily mean at 26 carries a daily maximum whose median runs 27.4 to 29.3 °C,
# which is the band Raymond, Matthews & Horton (2020) analyse as carrying serious
# health and productivity effects. The two neighbouring values were tried and
# rejected: 27 is nearly silent, firing on 0.1 % of days at Singapore and 0.0 %
# at Bamako while those places record hundreds of severe days, and 25 fires on
# 65 % of days at Singapore, which is no longer a warning.
#
# **30 marks the second.** The only threshold here taken from a measurement on
# human subjects rather than on weather: 30.55 +/- 0.98 °C is the critical wet
# bulb at which heat stress stops being compensable for young, healthy adults at
# the metabolic rate of ordinary daily activity (Vecellio et al. 2022, PSU HEAT).
# No subject reached the theoretical 35 °C of Sherwood & Huber (2010), and the
# limit is lower again for the old and the ill, so this describes the most
# resistant population. A *daily mean* above it means the whole day, night
# included, sat past that limit.
#
# **What is not settled, and rides on these two numbers.** On simulated days the
# wet bulb is built from the climate model's own humidity, whose bias is measured
# at one site: MRI_AGCM3_2_S runs 0.62 °C dry on the dew point at Strasbourg over
# 1979-2014, which puts its wet bulb 0.80 °C low there. The published range for
# raw CMIP6 is -0.5 to -2.5 °C over mid-latitude Eurasia, so that point is
# credible, but temperature and humidity biases compensate in the subtropics and
# the sign there is not settled by the literature — and the subtropics are where
# these thresholds fire. Sensitivity, at Dubai over 2040-2050: shifting the
# series by 0.6 °C moves the count above 26 by 11 %, and the count above 30 from
# 111 to 364. The first level is robust to the plausible bias; the second is not.
# The measurement is a step in itself and is not done. Until it is, these are
# constants an interface displays, not quantities a projection has earned.
HUMID_HEAT_C = 26.0
HUMID_HEAT_EXTREME_C = 30.0

# What the design document originally called a snow day, and what the criterion
# above is calibrated to reproduce. The climate model serves snow depth too
# irregularly to read it directly — hence the derived rule — but the reanalyses
# serve it faithfully, which is what makes the calibration possible at all.
SNOW_DEPTH_CM = 1.0
