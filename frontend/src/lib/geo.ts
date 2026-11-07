// Spherical-Earth helpers for drawing station geometry; [lon, lat] in degrees like GeoJSON.
export type LonLat = [number, number]

const EARTH_RADIUS_KM = 6371.0088
const rad = (deg: number) => (deg * Math.PI) / 180
const deg = (r: number) => (r * 180) / Math.PI

export function destination([lon, lat]: LonLat, bearingDeg: number, distanceKm: number): LonLat {
  const delta = distanceKm / EARTH_RADIUS_KM
  const theta = rad(bearingDeg)
  const phi1 = rad(lat)
  const lambda1 = rad(lon)
  const phi2 = Math.asin(Math.sin(phi1) * Math.cos(delta) + Math.cos(phi1) * Math.sin(delta) * Math.cos(theta))
  const lambda2 =
    lambda1 + Math.atan2(Math.sin(theta) * Math.sin(delta) * Math.cos(phi1), Math.cos(delta) - Math.sin(phi1) * Math.sin(phi2))
  return [((deg(lambda2) + 540) % 360) - 180, deg(phi2)]
}

export function distanceKm([lon1, lat1]: LonLat, [lon2, lat2]: LonLat): number {
  const dPhi = rad(lat2 - lat1)
  const dLambda = rad(lon2 - lon1)
  const a = Math.sin(dPhi / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLambda / 2) ** 2
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a))
}

function ring(center: LonLat, radiusKm: number, steps: number, startDeg = 0): LonLat[] {
  const points: LonLat[] = []
  for (let i = 0; i < steps; i++) points.push(destination(center, startDeg + (360 * i) / steps, radiusKm))
  points.push(points[0])
  return points
}

export const circlePolygon = (center: LonLat, radiusKm: number, steps = 96): LonLat[][] => [ring(center, radiusKm, steps)]

export const hexagon = (center: LonLat, radiusM: number): LonLat[][] => [ring(center, radiusM / 1000, 6, 30)]

// Shaft from the station along the azimuth plus a two-stroke head at the tip.
export function arrowLine(center: LonLat, azimuthDeg: number, lengthKm: number): LonLat[][] {
  const tip = destination(center, azimuthDeg, lengthKm)
  const head = lengthKm * 0.25
  return [
    [center, tip],
    [destination(tip, azimuthDeg + 150, head), tip, destination(tip, azimuthDeg - 150, head)],
  ]
}
