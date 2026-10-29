import React, { useEffect, useRef } from 'react'
import * as Cesium from 'cesium'
import { LayerState } from '../App'

type Props = { layers: LayerState; onSelect: (picked: any) => void }

export default function CesiumViewer({ layers, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewerRef = useRef<Cesium.Viewer | null>(null)
  const sampleSourceRef = useRef<Cesium.GeoJsonDataSource | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    if (viewerRef.current) return

    const viewer = new Cesium.Viewer(containerRef.current, {
      animation: false, timeline: false, baseLayerPicker: false, geocoder: false,
      sceneModePicker: false, navigationHelpButton: false, homeButton: true, infoBox: false,
      terrain: undefined
    })

    viewer.imageryLayers.removeAll()
    const osm = new Cesium.UrlTemplateImageryProvider({
      url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      credit: '© OpenStreetMap contributors'
    })
    viewer.imageryLayers.addImageryProvider(osm)

    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(-74.006, 40.7128, 2500000)
    })

    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction((movement: { position: Cesium.Cartesian2 }) => {
      const picked = viewer.scene.pick(movement.position)
      if (picked && (picked as any).id) onSelect((picked as any).id)
      else onSelect(null)
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    viewerRef.current = viewer
    return () => { handler.destroy(); viewer.destroy(); viewerRef.current = null }
  }, [])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return

    const toggle = async () => {
      if (layers.sampleGeoJSON) {
        if (!sampleSourceRef.current) {
          const src = await Cesium.GeoJsonDataSource.load('/data/sample.geojson', { clampToGround: false })
          viewer.dataSources.add(src)
          sampleSourceRef.current = src
        }
      } else {
        if (sampleSourceRef.current) {
          viewer.dataSources.remove(sampleSourceRef.current, true)
          sampleSourceRef.current = null
        }
      }
    }
    toggle()
  }, [layers.sampleGeoJSON])

  return <div className="viewer" ref={containerRef} />
}
