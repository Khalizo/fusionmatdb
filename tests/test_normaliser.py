from fusionmatdb.normalisation.material_normaliser import normalise_material_name, normalise_material_class

def test_canonical_eurofer():
    assert normalise_material_name("EUROFER97") == "EUROFER97"
    assert normalise_material_name("eurofer steel") == "EUROFER97"

def test_canonical_tungsten():
    assert normalise_material_name("pure W") == "W"
    assert normalise_material_name("Tungsten") == "W"
    assert normalise_material_name("K-doped W") == "K-doped W"

def test_rejects_ambiguous():
    assert normalise_material_name("steel") is None
    assert normalise_material_name("None") is None
    assert normalise_material_name("alloy") is None
    assert normalise_material_name(None) is None
    assert normalise_material_name("Fe") is None

def test_rejects_too_short():
    assert normalise_material_name("X") is None
    assert normalise_material_name("") is None

def test_passes_through_acceptable_unknown():
    # Unknown but specific-looking names should pass through
    result = normalise_material_name("W-2%Ta-0.5%Y2O3")
    assert result is not None
    assert len(result) > 2

def test_class_inference():
    assert normalise_material_class(None, "EUROFER97") == "RAFM_steel"
    assert normalise_material_class(None, "W") == "tungsten"
    assert normalise_material_class(None, "V-4Cr-4Ti") == "vanadium_alloy"
    assert normalise_material_class("tungsten_alloy", "W-3%Re") == "tungsten_alloy"
