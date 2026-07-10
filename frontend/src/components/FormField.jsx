// Generic labeled field. Handles the common input types so InteractionForm
// doesn't repeat the same label + input markup for every field.
function FormField({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  options = [],
  rows = 3,
}) {
  return (
    <div>
      <label className="field-label">{label}</label>

      {type === 'select' && (
        <select value={value} onChange={onChange} className="field-input">
          <option value="" disabled>
            Select {label.toLowerCase()}
          </option>
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      )}

      {type === 'textarea' && (
        <textarea
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          rows={rows}
          className="field-input resize-none"
        />
      )}

      {(type === 'text' || type === 'date' || type === 'time') && (
        <input
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className="field-input"
        />
      )}
    </div>
  )
}

export default FormField
