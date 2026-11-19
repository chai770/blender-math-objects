"""Generate an Antoine necklace in the active Blender scene.

Open this file in Blender's Scripting workspace, edit the settings below,
then click Run Script. Run it again after changing a setting. Use Material
Preview to see the link colors.
"""

from math import acos, atan2, cos, hypot, pi, sin, tau

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

LINKS = 20       # Tori in the base necklace. Use an even number of at least 8.
DEPTH = 2        # 1 = base necklace, 2 = LINKS² tori, 3 = LINKS³ tori.
GROUP_DEPTH = 1  # 0 = individual tori. Use DEPTH to select the whole necklace as one object.

# Repeat around each base necklace. Entries can be hex colors, existing
# Blender material names, or None for a link without a material.
MATERIAL_PATTERN = ("#CA8A41", "#467A8F")

# Dimensions in Blender units, except for the tube-to-ring radius ratio.
BASE_RADIUS = 5.0
TUBE_RATIO = 0.12
CLEARANCE = 0.001 * BASE_RADIUS

# Keep these names stable so rerunning the script can replace its own output.
COLLECTION_NAME = "Antoine's Necklace"
OWNER = "antoines_necklace_generator"


def ring_frames(radius, phases=(0.0, 0.0)):
    """Return the centers and orientations of a circular chain."""
    for index in range(LINKS):
        angle = tau * index / LINKS
        radial = Vector((cos(angle), sin(angle), 0))
        tangent = Vector((-sin(angle), cos(angle), 0))
        phase = phases[index % 2]
        across = radial if index % 2 == 0 else Vector((0, 0, 1))
        x = cos(phase) * tangent + sin(phase) * across
        y = -sin(phase) * tangent + cos(phase) * across
        basis = Matrix((x, y, tangent.cross(across))).transposed()
        frame = basis.to_4x4()
        frame.translation = radius * radial
        yield frame


def copies_have_clearance(placements, frames, link_radius):
    """Check all copy pairs up to the layout's rotational symmetry."""
    segments = 256
    samples = [
        Vector((link_radius * cos(tau * i / segments),
                link_radius * sin(tau * i / segments), 0))
        for i in range(segments)
    ]
    # Distance to a circle is 1-Lipschitz. Include the maximum arc
    # distance to the nearest sample and an allowance for mesh faceting.
    threshold = 2 * link_radius * TUBE_RATIO + CLEARANCE
    threshold += link_radius * (pi / segments + 0.005)
    centers = KDTree(len(placements))
    inverse_links = []
    for i, placement in enumerate(placements):
        centers.insert(placement.translation, i)
        inverse_links.append(placement.inverted())
    centers.balance()

    # Rotating the layout by two positions preserves all link orientations.
    for i in range(2):
        for j in range(i + 1, len(frames)):
            relative = frames[j].inverted() @ frames[i]
            for placement in placements:
                link = relative @ placement
                nearby = centers.find_range(link.translation, 2 * link_radius + threshold)
                for _, index, _ in nearby:
                    local = inverse_links[index] @ link
                    for sample in samples:
                        point = local @ sample
                        distance = hypot(hypot(point.x, point.y) - link_radius, point.z)
                        if distance <= threshold:
                            return False
    return True


def neighboring_circles_link(frames, major_radius):
    """Count crossings of each neighboring core through a copy's disk."""
    for i in range(2):
        relative = frames[i].inverted() @ frames[i + 1]
        x = relative.col[0].to_3d() * major_radius
        y = relative.col[1].to_3d() * major_radius
        center = relative.translation
        amplitude = hypot(x.z, y.z)
        if amplitude <= abs(center.z):
            return False
        phase = atan2(y.z, x.z)
        offset = acos(-center.z / amplitude)
        crossings = [
            center + x * cos(angle) + y * sin(angle)
            for angle in (phase - offset, phase + offset)
        ]
        if sum(point.length < major_radius for point in crossings) != 1:
            return False
    return True


def interweave(placements, major_radius, link_radius):
    # Bound the links by a tube around the circle through the copy centers.
    minor_radius = max(
        hypot(hypot(p.translation.x, p.translation.y) - major_radius, p.translation.z)
        for p in placements
    ) + link_radius * (1 + TUBE_RATIO)
    chord_per_radius = 2 * sin(pi / LINKS)
    separated = 2 * (major_radius + minor_radius + CLEARANCE)

    # Work in the chord distance between neighboring centers. A fixed
    # placement radius would change that distance whenever LINKS changes.
    preferred = 1.23282 * major_radius
    minimum = major_radius / cos(pi / LINKS)
    # Keep second-neighbor centers at least two major radii apart.
    # Sampling relative to the tube size keeps the search fine as links shrink.
    steps = max(80, min(240, int((separated - minimum) / (0.12 * link_radius))))
    distances = [minimum + (separated - minimum) * i / steps for i in range(steps)]
    distances.extend(major_radius * factor for factor in (
        1.23282, 1.2757330908, 1.38952, 1.6272879222
    ))

    # A fraction of one link spacing rotates the copy within its plane.
    link_angle = tau / LINKS
    phases_to_try = [(0.0, 0.0), (0.5, 0.5), (0.0, 0.5), (0.5, 0.0)]
    if len(placements) == LINKS:
        phases_to_try.extend(
            (i / 4, j / 4) for i in range(8) for j in range(8) if i % 4 or j % 4
        )
    fallback = None
    # Search near the successful 20-link spacing first. Include both tighter
    # and looser positions since the gaps between individual tori vary.
    for distance in sorted(distances, key=lambda value: abs(value - preferred)):
        radius = distance / chord_per_radius
        unrotated = list(ring_frames(radius))
        linked = neighboring_circles_link(unrotated, major_radius)
        if not linked and fallback and radius >= fallback[0]:
            continue
        for phase in phases_to_try if linked else [(0.0, 0.0)]:
            frames = unrotated
            if phase != (0.0, 0.0):
                frames = list(ring_frames(radius, tuple(p * link_angle for p in phase)))
            if not copies_have_clearance(placements, frames, link_radius):
                continue
            if linked:
                print(f"Interwoven copies: major {major_radius:.3f}, minor bound "
                      f"{minor_radius:.3f}, center spacing {distance:.3f}.")
                return frames, radius
            fallback = radius, frames

    print("Antoine's necklace: no clear interwoven placement found at this tier. "
          "Using separated copies.")
    if fallback:
        radius, frames = fallback
    else:
        radius = separated / chord_per_radius
        frames = ring_frames(radius)
    return frames, radius


def necklace_layers(link_radius):
    base = list(ring_frames(BASE_RADIUS))
    layers = [base]
    placements = base
    major_radius = BASE_RADIUS
    total_tiers = tier_count(DEPTH)
    for tier in range(1, total_tiers):
        frames, major_radius = interweave(placements, major_radius, link_radius)
        frames = list(frames)
        layers.append(frames)
        if tier + 1 < total_tiers:
            placements = [frame @ p for frame in frames for p in placements]
    return layers


def tier_count(depth):
    return depth


def torus_mesh(link_radius):
    major_segments, tube_segments = 96, 24
    vertices, faces = [], []
    for i in range(major_segments):
        u = tau * i / major_segments
        for j in range(tube_segments):
            v = tau * j / tube_segments
            radius = 1 + TUBE_RATIO * cos(v)
            vertices.append((
                link_radius * (radius * cos(u)),
                link_radius * (radius * sin(u)),
                link_radius * (TUBE_RATIO * sin(v)),
            ))
            a = i * tube_segments
            b = ((i + 1) % major_segments) * tube_segments
            k = (j + 1) % tube_segments
            faces.append((a + j, b + j, b + k, a + k))
    mesh = bpy.data.meshes.new("Antoine torus")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return mesh


def pattern_materials():
    if not MATERIAL_PATTERN:
        raise ValueError("MATERIAL_PATTERN needs at least one entry.")
    materials = []
    for entry in MATERIAL_PATTERN:
        if entry is None:
            materials.append(None)
            continue
        if not isinstance(entry, str):
            raise ValueError("Use a material name, #RRGGBB color, or None.")
        material = bpy.data.materials.get(entry)
        if material is None:
            if len(entry) != 7 or not entry.startswith("#"):
                raise ValueError(f"No Blender material named {entry!r}.")
            try:
                srgb = [int(entry[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            except ValueError as error:
                raise ValueError(f"Invalid hex color {entry!r}.") from error
            linear = tuple(
                c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                for c in srgb
            )
            material = bpy.data.materials.new(entry)
            material.diffuse_color = (*linear, 1)
            material.use_nodes = True
            shader = next(node for node in material.node_tree.nodes if
                          node.type == "BSDF_PRINCIPLED")
            shader.inputs["Base Color"].default_value = (*linear, 1)
        materials.append(material)
    return [materials[i % len(materials)] for i in range(LINKS)]


def add_link(collection, name, mesh, transform, material):
    obj = bpy.data.objects.new(name, mesh)
    obj[OWNER] = True
    collection.objects.link(obj)
    obj.matrix_world = transform
    if obj.material_slots:
        slot = obj.material_slots[0]
        slot.link = "OBJECT"
        slot.material = material
        obj.color = material.diffuse_color if material else (0.8, 0.8, 0.8, 1)


def add_instance(collection, name, source, transform):
    obj = bpy.data.objects.new(name, None)
    obj[OWNER] = True
    obj.instance_type = "COLLECTION"
    obj.instance_collection = source
    obj.empty_display_size = 0.25
    collection.objects.link(obj)
    obj.matrix_world = transform


def remove_output(collection):
    objects = [obj for obj in collection.all_objects if obj.get(OWNER)]
    meshes = {obj.data for obj in objects if obj.type == "MESH"}
    sources = {obj.instance_collection for obj in objects
               if obj.instance_collection and obj.instance_collection.get(OWNER)}
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for source in sources:
        if source.users == 0:
            remove_output(source)
    for child in list(collection.children):
        if child.get(OWNER) and not child.objects and not child.children:
            bpy.data.collections.remove(child)
    if not collection.objects and not collection.children:
        bpy.data.collections.remove(collection)
    for mesh in meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def generate():
    if type(DEPTH) is not int or not 1 <= DEPTH <= 3:
        raise ValueError("Set DEPTH to an integer from 1 to 3.")
    if type(GROUP_DEPTH) is not int or not 0 <= GROUP_DEPTH <= DEPTH:
        raise ValueError("Set GROUP_DEPTH to an integer between 0 and DEPTH.")
    if type(LINKS) is not int or LINKS < 8 or LINKS % 2:
        raise ValueError("Set LINKS to an even integer of at least 8.")
    if BASE_RADIUS <= 0 or CLEARANCE <= 0:
        raise ValueError("BASE_RADIUS and CLEARANCE must be positive.")

    link_radius = 1.33 * BASE_RADIUS * sin(pi / LINKS)
    layers = necklace_layers(link_radius)
    materials = pattern_materials()

    scene = bpy.context.scene
    for collection in list(scene.collection.children):
        if collection.get(OWNER):
            remove_output(collection)

    root = bpy.data.collections.new(COLLECTION_NAME)
    root[OWNER] = True
    scene.collection.children.link(root)
    mesh = torus_mesh(link_radius)
    first_material = next((material for material in materials if material is not None), None)
    if first_material is not None:
        mesh.materials.append(first_material)

    group_tiers = tier_count(GROUP_DEPTH)
    # Build each source collection once and reuse it at every placement.
    source = None
    for tier, frames in enumerate(layers[:group_tiers], 1):
        template = bpy.data.collections.new(f"Antoine's Necklace · Tier {tier} source")
        template[OWNER] = True
        for i, frame in enumerate(frames):
            if source is None:
                add_link(template, f"Link {i + 1:02d}", mesh, frame, materials[i])
            else:
                add_instance(template, f"Copy {i + 1:02d}", source, frame)
        source = template

    placements = [Matrix.Identity(4)]
    for frames in reversed(layers[group_tiers:]):
        placements = [parent @ frame for parent in placements for frame in frames]
    for i, frame in enumerate(placements):
        if source is None:
            add_link(root, f"Link {i + 1:04d}", mesh, frame, materials[i % LINKS])
        else:
            add_instance(root, f"Depth {GROUP_DEPTH} Necklace {i + 1:04d}", source, frame)

    print(f"Antoine's necklace: depth {DEPTH}, {LINKS ** len(layers):,} tori "
          f"in {len(placements):,} selectable objects.")


if __name__ == "__main__":
    generate()
