import { useState, useEffect, useRef } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  updateField,
  resetInteraction,
  setSelectedHcp,
  setEditingInteractionId,
  loadInteractionToEdit,
  showToast,
  cancelEdit,
} from "../redux/interactionSlice.js";
import {
  logInteraction,
  updateInteraction,
  searchHCP,
  createHCP,
  getInteractionHistory,
} from "../services/api.js";
import FormField from "./FormField.jsx";


const INTERACTION_TYPES = ["Meeting", "Call", "Email", "Conference"];
const SENTIMENT_OPTIONS = ["Positive", "Neutral", "Negative"];

function InteractionForm() {
  const dispatch = useDispatch();
  const interaction = useSelector((state) => state.interaction);

  const [isSaving, setIsSaving] = useState(false);

  // HCP Autocomplete states
  const [searchResults, setSearchResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  // HCP Inline Creation Form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newHcp, setNewHcp] = useState({
    name: "",
    hospital: "",
    specialization: "",
    city: "",
  });

  // Interaction History states
  const [historyList, setHistoryList] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Refs for debouncing, focus, and clicks
  const searchTimeoutRef = useRef(null);
  const abortControllerRef = useRef(null);
  const dropdownRef = useRef(null);
  const searchInputRef = useRef(null);
  const typeSelectRef = useRef(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  // Reactive Effect: trigger backend search when interaction.hcpName changes
  useEffect(() => {
    // If selectedHcp's name is already equal to hcpName, do not re-trigger search
    if (
      interaction.selectedHcp &&
      interaction.selectedHcp.name === interaction.hcpName
    ) {
      return;
    }

    const val = interaction.hcpName;
    if (!val || val.trim().length <= 1) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }

    setIsSearching(true);
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    searchTimeoutRef.current = setTimeout(async () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const res = await searchHCP(val, controller.signal);
        const matches = res.data || [];
        setSearchResults(matches);

        // If a unique match exists (matches.length === 1), select it automatically!
        if (matches.length === 1) {
          dispatch(setSelectedHcp(matches[0]));
          setShowDropdown(false);
        } else {
          setShowDropdown(true);
        }
      } catch (err) {
        if (err.name !== "CanceledError" && err.name !== "AbortError") {
          // Quiet fail
        }
      } finally {
        setIsSearching(false);
      }
    }, 400);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [interaction.hcpName, dispatch]);

  const handleHcpSearchChange = (e) => {
    const val = e.target.value;
    if (interaction.selectedHcp && interaction.selectedHcp.name !== val) {
      dispatch(setSelectedHcp(null));
    }
    dispatch(updateField({ field: "hcpName", value: val }));
  };

  const handleSelectHcp = (hcp) => {
    dispatch(setSelectedHcp(hcp));
    setShowDropdown(false);
    setSearchResults([]);
    setShowCreateForm(false);
  };

  const handleClearHcp = () => {
    dispatch(setSelectedHcp(null));
    dispatch(updateField({ field: "hcpName", value: "" }));
    setSearchResults([]);
    setShowDropdown(false);
    setTimeout(() => searchInputRef.current?.focus(), 50);
  };

  const handleTriggerCreateHcp = () => {
    setNewHcp({
      name: interaction.hcpName || "",
      hospital: "",
      specialization: "",
      city: "",
    });
    setShowCreateForm(true);
    setShowDropdown(false);
  };

  const handleSaveNewHcp = async () => {
    if (!newHcp.name.trim() || !newHcp.hospital.trim()) {
      dispatch(
        showToast({
          message: "Doctor Name and Hospital / Clinic are required.",
          type: "error",
        }),
      );
      return;
    }
    try {
      const res = await createHCP(newHcp);
      handleSelectHcp(res.data);
      dispatch(
        showToast({
          message: "HCP created successfully!",
          type: "success",
        }),
      );
    } catch (err) {
      dispatch(
        showToast({
          message: "Failed to create HCP.",
          type: "error",
        }),
      );
    }
  };

  // Fetch history when selectedHcp changes
  const fetchHistory = async (hcpId) => {
    if (!hcpId) return;
    setIsLoadingHistory(true);
    try {
      const response = await getInteractionHistory(hcpId);
      setHistoryList(response.data || []);
    } catch (err) {
      // Quiet fail
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (interaction.selectedHcp) {
      fetchHistory(interaction.selectedHcp.id);
    } else {
      setHistoryList([]);
    }
  }, [interaction.selectedHcp]);

  const handleFieldChange = (field) => (e) => {
    dispatch(updateField({ field, value: e.target.value }));
  };

  // Shared payload builder
  const buildInteractionPayload = () => {
    return {
      hcp_id: interaction.selectedHcp ? interaction.selectedHcp.id : null,
      interaction_type: interaction.interactionType,
      interaction_date: interaction.date || null,
      interaction_time: interaction.time || null,
      meeting_location: interaction.meetingLocation || "",
      ai_meeting_location: interaction.aiMeetingLocation || "",
      attendees: interaction.attendees,
      topics_discussed: interaction.topicsDiscussed,
      ai_summary: interaction.aiSummary,
      sentiment: interaction.sentiment,
      outcomes: interaction.outcomes,
      follow_up_actions: interaction.followUpActions,
      materials_shared: interaction.materialsShared
        ? interaction.materialsShared
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
      samples_distributed: interaction.samplesDistributed
        ? interaction.samplesDistributed
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
      ai_suggestions: interaction.aiSuggestions || [],
    };
  };

  const handleSave = async () => {
    if (!interaction.selectedHcp) {
      dispatch(
        showToast({
          message: "Please select or create an HCP first.",
          type: "error",
        }),
      );
      return;
    }
    setIsSaving(true);
    const payload = buildInteractionPayload();
    // Synchronize HCP master data with AI extraction
    if (
      interaction.selectedHcp &&
      interaction.aiHospital &&
      interaction.aiHospital.trim() &&
      interaction.aiHospital !== interaction.selectedHcp.hospital
    ) {
      

      dispatch(
        setSelectedHcp({
          ...interaction.selectedHcp,
          hospital: interaction.aiHospital,
        }),
      );
    }

    try {
      if (interaction.editingInteractionId) {
        await updateInteraction(interaction.editingInteractionId, payload);
        dispatch(
          showToast({
            message: "Interaction updated successfully!",
            type: "success",
          }),
        );
      } else {
        await logInteraction(payload);
        dispatch(
          showToast({
            message: "Interaction saved successfully!",
            type: "success",
          }),
        );
      }

      const currentHcp = interaction.selectedHcp;
      dispatch(resetInteraction());
      fetchHistory(currentHcp.id);
    } catch (error) {
      dispatch(
        showToast({
          message: "Failed to save interaction.",
          type: "error",
        }),
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleTriggerEdit = (hist) => {
    dispatch(loadInteractionToEdit(hist));
    window.scrollTo({ top: 0, behavior: "smooth" });

    // Focus the first editable element
    setTimeout(() => {
      const selectElem = document.querySelector("select.field-input");
      if (selectElem) selectElem.focus();
    }, 100);
  };

  return (
    <section className="rounded-card border border-gray-200 bg-gray-50 p-6 shadow-card">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-base font-semibold text-gray-900">
          {interaction.editingInteractionId
            ? "Edit Interaction Details"
            : "Interaction Details"}
        </h2>
        {interaction.editingInteractionId && (
          <button
            type="button"
            onClick={() => {
              dispatch(cancelEdit());
            }}
            className="rounded border border-gray-300 bg-white px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50"
          >
            Cancel Edit
          </button>
        )}
      </div>

      <div className="space-y-5">
        {/* HCP Autocomplete Selection + Interaction Type */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="relative" ref={dropdownRef}>
            <label className="field-label">HCP Name *</label>
            {interaction.selectedHcp ? (
              <div className="flex items-center justify-between rounded-lg border border-primary bg-primary/5 p-2 text-sm text-gray-800">
                <div>
                  <span className="font-semibold text-primary">
                    {interaction.selectedHcp.name}
                  </span>
                  <span className="ml-1 text-xs text-gray-500">
                    ({interaction.selectedHcp.hospital || "No Hospital"})
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleClearHcp}
                  className="text-xs font-semibold text-red-500 hover:text-red-700"
                >
                  Clear
                </button>
              </div>
            ) : (
              <>
                <div className="relative">
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={interaction.hcpName}
                    onChange={handleHcpSearchChange}
                    onFocus={() => {
                      if (searchResults.length > 0) setShowDropdown(true);
                    }}
                    placeholder="Search by doctor, hospital, spec..."
                    className="field-input pr-10"
                  />
                  {isSearching && (
                    <div className="absolute right-3 top-2.5 flex h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
                  )}
                </div>

                {showDropdown && (
                  <div className="absolute z-10 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                    {searchResults.length > 0 ? (
                      searchResults.map((hcp) => (
                        <div
                          key={hcp.id}
                          onClick={() => handleSelectHcp(hcp)}
                          className="cursor-pointer px-4 py-2 hover:bg-gray-100 text-sm text-gray-700"
                        >
                          <div className="font-semibold">{hcp.name}</div>
                          <div className="text-xs text-gray-500">
                            {hcp.hospital} •{" "}
                            {hcp.specialization || "General Medicine"}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="px-4 py-2 text-sm text-gray-500 italic">
                        No matches found
                      </div>
                    )}
                    <div
                      onClick={handleTriggerCreateHcp}
                      className="cursor-pointer border-t border-gray-100 px-4 py-2 hover:bg-gray-100 text-sm font-semibold text-primary text-center"
                    >
                      + Create New HCP
                    </div>
                  </div>
                )}

                {/* Explicit creation confirmation block */}
                {interaction.hcpName.trim() &&
                  !isSearching &&
                  searchResults.length === 0 && (
                    <div className="mt-2 rounded bg-amber-50 p-2.5 text-xs border border-amber-200 text-amber-800 flex justify-between items-center">
                      <span>Doctor not found. Create new HCP?</span>
                      <button
                        type="button"
                        onClick={handleTriggerCreateHcp}
                        className="rounded bg-amber-600 px-2.5 py-1 text-white font-semibold hover:bg-amber-700 transition-colors"
                      >
                        Yes, Create
                      </button>
                    </div>
                  )}
              </>
            )}

            {/* Inline creation form */}
            {showCreateForm && (
              <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm mt-3 space-y-3">
                <h3 className="text-sm font-semibold text-gray-800">
                  Create New HCP
                </h3>
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-1">
                    Doctor Name *
                  </label>
                  <input
                    type="text"
                    value={newHcp.name}
                    onChange={(e) =>
                      setNewHcp({ ...newHcp, name: e.target.value })
                    }
                    className="field-input text-xs"
                    placeholder="Dr. Raj Sharma"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-1">
                    Hospital / Clinic *
                  </label>
                  <input
                    type="text"
                    value={newHcp.hospital}
                    onChange={(e) =>
                      setNewHcp({ ...newHcp, hospital: e.target.value })
                    }
                    className="field-input text-xs"
                    placeholder="Apollo Hospital"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-1">
                    Specialization
                  </label>
                  <input
                    type="text"
                    value={newHcp.specialization}
                    onChange={(e) =>
                      setNewHcp({ ...newHcp, specialization: e.target.value })
                    }
                    className="field-input text-xs"
                    placeholder="Cardiology"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    value={newHcp.city}
                    onChange={(e) =>
                      setNewHcp({ ...newHcp, city: e.target.value })
                    }
                    className="field-input text-xs"
                    placeholder="Delhi"
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="rounded border border-gray-300 bg-white px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveNewHcp}
                    className="rounded bg-primary px-2.5 py-1 text-xs text-white hover:bg-primary-hover"
                  >
                    Save Doctor
                  </button>
                </div>
              </div>
            )}
          </div>

          <FormField
            ref={typeSelectRef}
            label="Interaction Type"
            type="select"
            value={interaction.interactionType}
            onChange={handleFieldChange("interactionType")}
            options={INTERACTION_TYPES}
          />
        </div>

        {/* Date + Time */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormField
            label="Date"
            type="date"
            value={interaction.date}
            onChange={handleFieldChange("date")}
          />
          <FormField
            label="Time"
            type="time"
            value={interaction.time}
            onChange={handleFieldChange("time")}
          />
        </div>

        {/* Meeting Location & Attendees */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormField
            label="Meeting Location"
            value={interaction.meetingLocation}
            onChange={handleFieldChange("meetingLocation")}
            placeholder="e.g. Apollo Hospital Clinic Room 3"
          />
          <FormField
            label="Attendees"
            value={interaction.attendees}
            onChange={handleFieldChange("attendees")}
            placeholder="Enter names..."
          />
        </div>

        {/* Topics Discussed */}
        <div>
          <FormField
            label="Topics Discussed"
            type="textarea"
            value={interaction.topicsDiscussed}
            onChange={handleFieldChange("topicsDiscussed")}
            placeholder="Enter key discussion points..."
          />
          <button
            type="button"
            className="mt-2 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100"
          >
            🎙 Summarize from Voice Note (Requires Consent)
          </button>
        </div>

        {/* Materials Shared / Samples Distributed */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-800">
            Materials Shared / Samples Distributed
          </h3>

          <div className="mb-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                Materials Shared
              </span>
              <button
                type="button"
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-hover"
              >
                Search/Add
              </button>
            </div>
            <p className="mt-1 text-xs italic text-gray-400">
              {interaction.materialsShared || "No materials added."}
            </p>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                Samples Distributed
              </span>
              <button
                type="button"
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-hover"
              >
                Add Sample
              </button>
            </div>
            <p className="mt-1 text-xs italic text-gray-400">
              {interaction.samplesDistributed || "No samples added."}
            </p>
          </div>
        </div>

        {/* Observed/Inferred HCP Sentiment */}
        <div>
          <label className="field-label">Observed/Inferred HCP Sentiment</label>
          <div className="flex gap-6">
            {SENTIMENT_OPTIONS.map((option) => (
              <label
                key={option}
                className="flex items-center gap-2 text-sm text-gray-700"
              >
                <input
                  type="radio"
                  name="sentiment"
                  value={option}
                  checked={interaction.sentiment.trim() === option}
                  onChange={handleFieldChange("sentiment")}
                />
                {option}
              </label>
            ))}
          </div>
        </div>

        {/* Outcomes */}
        <FormField
          label="Outcomes"
          type="textarea"
          value={interaction.outcomes}
          onChange={handleFieldChange("outcomes")}
          placeholder="Key outcomes or agreements..."
        />

        {/* Follow-up Actions */}
        <FormField
          label="Follow-up Actions"
          type="textarea"
          value={interaction.followUpActions}
          onChange={handleFieldChange("followUpActions")}
          placeholder="Enter next steps or tasks..."
        />

        {/* AI Suggested Follow-ups */}
        <div>
          <label className="field-label">AI Suggested Follow-ups</label>
          {interaction.aiSuggestions.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 text-sm text-primary">
              {interaction.aiSuggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-gray-400">
              AI suggestions will appear here once available.
            </p>
          )}
        </div>

        {/* Save/Update Button */}
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className="w-full rounded-lg bg-primary py-2.5 text-sm font-semibold text-white shadow-card transition-colors hover:bg-primary-hover disabled:opacity-60"
        >
          {isSaving
            ? "Saving..."
            : interaction.editingInteractionId
              ? "Update Interaction"
              : "Save Interaction"}
        </button>
      </div>

      {/* Interaction History list */}
      {interaction.selectedHcp && (
        <div className="mt-8 border-t border-gray-200 pt-6">
          <h3 className="mb-4 text-base font-semibold text-gray-900">
            Interaction History: {interaction.selectedHcp.name}
          </h3>
          {isLoadingHistory ? (
            <p className="text-sm text-gray-500">Loading history...</p>
          ) : historyList.length === 0 ? (
            <p className="text-sm text-gray-500 italic">
              No previous interactions found.
            </p>
          ) : (
            <div className="space-y-4">
              {historyList.map((hist) => (
                <div
                  key={hist.id}
                  className="rounded-lg border border-gray-150 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold text-gray-800">
                      {hist.interaction_date || "No Date"} @{" "}
                      {hist.interaction_time || "No Time"}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold ${
                        hist.sentiment === "Positive"
                          ? "bg-green-100 text-green-800"
                          : hist.sentiment === "Negative"
                            ? "bg-red-100 text-red-800"
                            : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {hist.sentiment || "Neutral"}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-2 mb-3">
                    <span className="rounded bg-gray-100 text-gray-700 px-2 py-0.5 text-[10px] font-medium">
                      Type: {hist.interaction_type || "Meeting"}
                    </span>
                    {hist.meeting_location && (
                      <span className="rounded bg-amber-50 text-amber-700 px-2 py-0.5 text-[10px] font-medium">
                        📍 {hist.meeting_location}
                      </span>
                    )}
                    {hist.created_at && (
                      <span className="rounded bg-teal-50 text-teal-700 px-2 py-0.5 text-[10px] font-medium">
                        Logged: {new Date(hist.created_at).toLocaleString()}
                      </span>
                    )}
                  </div>

                  {hist.topics_discussed && (
                    <p className="text-xs text-gray-600 mb-2 leading-relaxed">
                      <strong>Topics:</strong> {hist.topics_discussed}
                    </p>
                  )}
                  {hist.ai_summary && (
                    <p className="text-xs text-gray-600 mb-2 leading-relaxed">
                      <strong>Summary:</strong> {hist.ai_summary}
                    </p>
                  )}
                  {hist.outcomes && (
                    <p className="text-xs text-gray-600 mb-2 leading-relaxed">
                      <strong>Outcomes:</strong> {hist.outcomes}
                    </p>
                  )}
                  {hist.follow_up_actions && (
                    <p className="text-xs text-gray-600 mb-2 leading-relaxed">
                      <strong>Follow-up:</strong> {hist.follow_up_actions}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2 mt-2">
                    {hist.materials && hist.materials.length > 0 && (
                      <span className="rounded bg-blue-50 text-blue-700 px-2 py-0.5 text-[10px] font-medium">
                        Materials:{" "}
                        {hist.materials.map((m) => m.material_name).join(", ")}
                      </span>
                    )}
                    {hist.samples && hist.samples.length > 0 && (
                      <span className="rounded bg-purple-50 text-purple-700 px-2 py-0.5 text-[10px] font-medium">
                        Samples:{" "}
                        {hist.samples
                          .map((s) => `${s.quantity}x ${s.sample_name}`)
                          .join(", ")}
                      </span>
                    )}
                  </div>
                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      onClick={() => handleTriggerEdit(hist)}
                      className="rounded bg-primary px-3 py-1 text-xs text-white hover:bg-primary-hover"
                    >
                      Edit Interaction
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default InteractionForm;
