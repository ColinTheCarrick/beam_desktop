# Beam Designer

## Purpose
Create shear, moment, and deflection diagrams for a beam and provide
preliminary bending and deflection checks. Results must state their assumptions
and limitations; they are not a complete code-compliant beam design.

## Initial scope
- Simply supported or cantilever beams.
- Point loads and uniform loads.
- Steel W-shapes for the initial release, using a small prototype dataset.
  Until verified catalog data is added, every demo shape must be conspicuously
  labeled as synthetic and unsuitable for real design. Add lumber in a later
  phase after its size, species, grade, and property data are defined.
- Continuous beams and buckling checks are out of scope for the initial release.

## Inputs and assumptions
- Support type and span, entered in feet.
- Point and uniform loads, with locations and extents where applicable.
- Use sliders with live readouts: span 0-100 ft in 0.5 ft steps; point loads
  -20 to 20 kip in 0.25 kip steps; uniform loads -5 to 5 kip/ft in 0.1 kip/ft
  steps; load positions 0 to the current span in 0.25 ft steps. A zero span is
  invalid for analysis.
- If the span is reduced, clamp point positions to the new span and adjust
  uniform-load extents so they remain within it.
- A steel W-shape with, at minimum, designation, weight, dimensions,
  strong-axis moment of inertia (Ix), and section modulus (Sx). Prototype
  properties are explicitly synthetic. Before real use, replace them with
  verified data from a documented, versioned source.
- The prototype material defaults are A992, Fy = 50 ksi, and E = 29,000 ksi;
  identify them as demonstration assumptions.
- The user may enter an allowable bending stress for a preliminary stress
  screen. Leave it unset by default; do not infer a code allowable from Fy.
- Use US customary units and label values and results (for example: ft, kip,
  kip/ft, in, and ksi). Define the load and diagram sign conventions, including
  whether upward loads are supported.
- State clearly whether beam self-weight is included. The initial validation
  case excludes self-weight. The prototype excludes it and says so in the UI.
- Use the strong axis by default and identify the assumed bending axis.
- Treat positive point and uniform loads as downward and negative values as
  upward.

## Calculations
- Reactions, shear, and moment from statics.
- Beam deflection for the supported loads and stated support conditions.
- Bending stress, fb = M/S, compared with the specified allowable bending
  stress. Show the stress even if no allowable is entered; only show a
  comparison when the user supplies one. This is a preliminary stress screen,
  not a design-capacity check; it does not account for buckling or establish
  overall member adequacy.
- Maximum deflection compared with a configurable limit. Use L/360 as the
  initial default, and show that the appropriate limit depends on the
  application.
- State which loads are included in each strength and serviceability result.

## Outputs
- The beam and its applied loads, plus shear, moment, and deflection diagrams.
- Support reactions.
- Maximum shear, moment, and deflection, with their locations and units.
- Clearly qualified bending and deflection results, assumptions, and any
  limitations; do not present them as a general declaration that a beam is safe.

## Look and feel
Clean and professional, with an example beam loaded when it opens.
Add a header color-scheme dropdown with Light, Dark mode, Night mode, Ocean,
Sunset, and Forest themes. Apply each theme consistently to the page, controls,
notices, and analysis diagrams.

## Validation
For a 20 ft simply supported W12x26 with a 1 kip/ft uniform load, verify
maximum moment = 50.0 kip-ft and maximum deflection = 0.609 in. The reference
case excludes beam self-weight. The prototype uses synthetic Ix = 204 in4
and E = 29,000 ksi to match the deflection reference; this checks calculation
behavior only, not the properties of a real W12x26.

Add validation cases for a cantilever and a point load. Check reactions and
force/moment equilibrium as well as diagram results.

## Future work
- Add lumber sizes with actual dimensions, species, grade, bending value (Fb),
  modulus of elasticity (E), and documented property sources.
- Consider additional design checks, such as shear, bearing, and buckling,
  before expanding claims about whether a beam is adequate.
