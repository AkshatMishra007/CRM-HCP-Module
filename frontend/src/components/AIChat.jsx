import { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  addChatMessage,
  updateField,
  setAiSuggestions,
  setAiSummary,
  setSelectedHcp,
} from "../redux/interactionSlice";
import { sendChat } from "../services/api";

function AIChat() {
  const dispatch = useDispatch();

  const chatMessages = useSelector((state) => state.interaction.chatMessages);

  const [draft, setDraft] = useState("");

  const handleSend = async () => {
    const message = draft.trim();

    if (!message) return;

    // Add user message
    dispatch(
      addChatMessage({
        sender: "user",
        text: message,
      }),
    );

    setDraft("");

    try {
      const response = await sendChat(message);

      const ai = response.data;

      const data = ai.extracted_data;
      // Populate extracted doctor name into Redux hcpName
      dispatch(
        updateField({
          field: "hcpName",
          value: data.hcp_name || "",
        }),
      );
      dispatch(
        updateField({
          field: "aiHospital",
          value: data.hospital || "",
        }),
      );
      dispatch(setSelectedHcp(null));

      let interactionType = "";

      if (data.interaction_type) {
        const type = data.interaction_type.toLowerCase();

        if (type.includes("meeting")) interactionType = "Meeting";
        else if (type.includes("call")) interactionType = "Call";
        else if (type.includes("email")) interactionType = "Email";
        else if (type.includes("conference")) interactionType = "Conference";
      }

      dispatch(
        updateField({
          field: "interactionType",
          value: interactionType,
        }),
      );

      let formattedDate = "";

      if (data.interaction_date) {
        const d = new Date(data.interaction_date);

        if (!isNaN(d.getTime())) {
          formattedDate = d.toISOString().split("T")[0];
        }
      }

      dispatch(
        updateField({
          field: "date",
          value: formattedDate,
        }),
      );
      dispatch(
        updateField({
          field: "time",
          value: data.interaction_time || "",
        }),
      );

      const location =
        data.meeting_location?.trim() || data.hospital?.trim() || "";

      dispatch(
        updateField({
          field: "meetingLocation",
          value: location,
        }),
      );

      dispatch(
        updateField({
          field: "aiMeetingLocation",
          value: location,
        }),
      );
      dispatch(
        updateField({
          field: "topicsDiscussed",
          value: data.topics_discussed || "",
        }),
      );

      let sentiment = "";

      if (data.sentiment) {
        const s = data.sentiment.toLowerCase();

        if (
          s.includes("positive") ||
          s.includes("interest") ||
          s.includes("interested") ||
          s.includes("strong")
        ) {
          sentiment = "Positive";
        } else if (
          s.includes("negative") ||
          s.includes("reject") ||
          s.includes("concern")
        ) {
          sentiment = "Negative";
        } else {
          sentiment = "Neutral";
        }
      }

      dispatch(
        updateField({
          field: "sentiment",
          value: sentiment,
        }),
      );

      dispatch(
        updateField({
          field: "outcomes",
          value: data.outcomes || "",
        }),
      );

      dispatch(
        updateField({
          field: "followUpActions",
          value: data.follow_up_actions || "",
        }),
      );

      // Do not duplicate HCP name inside attendees unless it's explicitly different
      dispatch(
        updateField({
          field: "attendees",
          value:
            data.attendees && data.attendees !== data.hcp_name
              ? data.attendees
              : "",
        }),
      );

      dispatch(
        updateField({
          field: "materialsShared",
          value: data.materials_shared?.join(", ") || "",
        }),
      );

      dispatch(
        updateField({
          field: "samplesDistributed",
          value: data.samples_distributed?.join(", ") || "",
        }),
      );

      // Save AI suggestions
      dispatch(setAiSuggestions(ai.suggestions || []));
      dispatch(setAiSummary(ai.summary || ""));

      // Build assistant message
      let assistantResponse = ai.summary || "";

      if (
        ai.suggestions &&
        Array.isArray(ai.suggestions) &&
        ai.suggestions.length > 0
      ) {
        assistantResponse += "\n\n🎯 Recommended Next Actions\n\n";

        ai.suggestions.forEach((item, index) => {
          assistantResponse += `${index + 1}. ${item}\n`;
        });
      }
     
      // Add assistant message to chat
      dispatch(
        addChatMessage({
          sender: "assistant",
          text: assistantResponse,
        }),
      );
    } catch (error) {
      console.error(error);

      dispatch(
        addChatMessage({
          sender: "assistant",
          text: "Unable to connect to AI assistant.",
        }),
      );
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <section className="flex h-full flex-col rounded-card border border-gray-200 bg-gray-50 p-4 shadow-card">
      <div className="mb-3">
        <h2 className="text-base font-semibold text-gray-900">AI Assistant</h2>

        <p className="text-xs text-gray-500">Log interaction via chat</p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-gray-200 bg-white p-3">
        <div className="rounded-lg bg-gray-100 p-3 text-sm text-gray-700">
          Log interaction details here (e.g., "Met Dr. Smith, discussed Product
          X efficacy, positive sentiment, shared brochure")
        </div>

        {chatMessages.map((msg, index) => (
          <div
            key={index}
            className={`max-w-[85%] rounded-lg p-3 text-sm ${
              msg.sender === "user"
                ? "ml-auto bg-primary text-white"
                : "bg-gray-100 text-gray-700"
            }`}
          >
            {msg.text}
          </div>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe interaction..."
          className="field-input"
        />

        <button
          type="button"
          onClick={handleSend}
          className="whitespace-nowrap rounded-lg bg-gray-400 px-4 py-2 text-sm font-medium text-white hover:bg-gray-500"
        >
          Log
        </button>
      </div>
    </section>
  );
}

export default AIChat;
