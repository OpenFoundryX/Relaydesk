/**
 * The IANA zones offered on the account page.
 *
 * The previous list was five hand-written strings in lib/mock/settings.ts
 * that glued the offset onto the zone name -- "Asia/Calcutta  GMT+5:30" --
 * and the Select used each one as both its label and its value. That was
 * invisible for as long as nothing read the value; once the API started
 * validating what it was sent, every save was refused as not a recognised
 * IANA time zone.
 */
export interface TimeZoneOption {
  id: string;
  label: string;
}

/**
 * `current` is always included. This runtime's ICU data canonicalises some
 * zones (it offers Asia/Calcutta, not Asia/Kolkata) and omits UTC, which is
 * the column default -- so a legitimately stored value can be absent from
 * the generated list, and a Select whose value is not among its items
 * renders blank.
 */
export function timeZoneOptions(current: string): TimeZoneOption[] {
  const ids = new Set<string>(Intl.supportedValuesOf("timeZone"));
  ids.add("UTC");
  if (current) ids.add(current);
  return [...ids]
    .sort((a, b) => a.localeCompare(b))
    .map((id) => ({ id, label: `${id}  ${offsetFor(id)}`.trimEnd() }));
}

function offsetFor(id: string): string {
  try {
    return (
      new Intl.DateTimeFormat("en-US", {
        timeZone: id,
        timeZoneName: "longOffset",
      })
        .formatToParts(new Date())
        .find((part) => part.type === "timeZoneName")?.value ?? ""
    );
  } catch {
    // A zone this runtime cannot format is still worth offering: the API
    // validates against Python's tzdata, not this list, and a missing
    // offset suffix is cosmetic.
    return "";
  }
}
