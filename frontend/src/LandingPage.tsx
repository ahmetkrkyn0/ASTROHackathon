import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

interface LandingPageProps {
  onExplore: () => void
}

const BASE_CAMERA_DISTANCE = 3.42
const EXPLORE_DURATION_MS = 1350
const MOON_TEXTURE_PATH = '/textures/moon-lroc-wac-global-1024.jpg'

let cachedGlowTexture: THREE.CanvasTexture | null = null
let cachedMoonTexturePromise: Promise<THREE.CanvasTexture> | null = null

export default function LandingPage({ onExplore }: LandingPageProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isExploring, setIsExploring] = useState(false)
  const exploringRef = useRef(false)

  useEffect(() => {
    exploringRef.current = isExploring
  }, [isExploring])

  useEffect(() => {
    if (!isExploring) {
      return
    }

    const timer = window.setTimeout(() => onExplore(), EXPLORE_DURATION_MS)
    return () => window.clearTimeout(timer)
  }, [isExploring, onExplore])

  useEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }

    const scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(0x03040a, 0.026)

    const camera = new THREE.PerspectiveCamera(
      34,
      Math.max(container.clientWidth, 1) / Math.max(container.clientHeight, 1),
      0.1,
      120,
    )
    camera.position.set(0, 0.04, BASE_CAMERA_DISTANCE)

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2.4))
    renderer.setSize(container.clientWidth, container.clientHeight, false)
    renderer.setClearColor(0x020308, 1)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2
    renderer.domElement.style.width = '100%'
    renderer.domElement.style.height = '100%'
    renderer.domElement.style.display = 'block'
    renderer.domElement.style.touchAction = 'none'
    container.appendChild(renderer.domElement)

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.52)
    const hemisphereLight = new THREE.HemisphereLight(0xe4e9ff, 0x10131f, 0.38)
    const keyLight = new THREE.DirectionalLight(0xfff1d6, 1.12)
    keyLight.position.set(4.4, 1.6, 4.2)
    const fillLight = new THREE.DirectionalLight(0x90a4ff, 0.2)
    fillLight.position.set(-4.5, -1.6, -3.3)
    scene.add(ambientLight, hemisphereLight, keyLight, fillLight)

    const starField = createStarField(5600, 32, 92, 0.038, [0xfafcff, 0x9db0ff, 0xd7dceb])
    const starFieldFar = createStarField(2600, 52, 128, 0.07, [0xffffff, 0xc8d1ff])
    scene.add(starField, starFieldFar)

    const moonGroup = new THREE.Group()
    moonGroup.position.set(0.12, 0.02, 0)
    scene.add(moonGroup)

    const moonGeometry = new THREE.SphereGeometry(1, 192, 192)
    const moonMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.96,
      metalness: 0,
      emissive: new THREE.Color(0x8b93a8),
      emissiveIntensity: 0.34,
    })
    const moonMesh = new THREE.Mesh(moonGeometry, moonMaterial)
    moonMesh.rotation.set(0.05, -0.18, 0.02)
    moonGroup.add(moonMesh)

    const rimMaterial = new THREE.MeshBasicMaterial({
      color: 0x8ea0ff,
      transparent: true,
      opacity: 0.035,
      side: THREE.BackSide,
      depthWrite: false,
    })
    const rimMesh = new THREE.Mesh(moonGeometry.clone(), rimMaterial)
    rimMesh.scale.setScalar(1.016)
    moonMesh.add(rimMesh)

    const glowMaterial = new THREE.SpriteMaterial({
      map: getGlowTexture(),
      color: 0xa8b4ff,
      transparent: true,
      opacity: 0.36,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const glowSprite = new THREE.Sprite(glowMaterial)
    glowSprite.position.set(-0.04, 0.03, -0.44)
    glowSprite.scale.set(4.7, 4.7, 1)
    moonGroup.add(glowSprite)

    let textureLoadCancelled = false
    void getMoonTexture(renderer.capabilities.getMaxAnisotropy()).then((texture) => {
      if (textureLoadCancelled) {
        return
      }

      moonMaterial.map = texture
      moonMaterial.emissiveMap = texture
      moonMaterial.needsUpdate = true
    })

    const state = {
      dragging: false,
      prevX: 0,
      prevY: 0,
      velocityX: 0,
      velocityY: 0,
      targetDistance: BASE_CAMERA_DISTANCE,
      currentDistance: BASE_CAMERA_DISTANCE,
      exploreProgress: 0,
    }

    const clampPitch = (value: number) => THREE.MathUtils.clamp(value, -0.72, 0.72)

    const releasePointer = (event?: PointerEvent) => {
      state.dragging = false
      if (event && renderer.domElement.hasPointerCapture(event.pointerId)) {
        renderer.domElement.releasePointerCapture(event.pointerId)
      }
    }

    const handlePointerLeave = () => {
      releasePointer()
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (exploringRef.current) {
        return
      }

      state.dragging = true
      state.prevX = event.clientX
      state.prevY = event.clientY
      renderer.domElement.setPointerCapture(event.pointerId)
    }

    const handlePointerMove = (event: PointerEvent) => {
      if (!state.dragging || exploringRef.current) {
        return
      }

      const deltaX = event.clientX - state.prevX
      const deltaY = event.clientY - state.prevY

      state.velocityY = deltaX * 0.0034
      state.velocityX = deltaY * 0.0028
      moonMesh.rotation.y += state.velocityY
      moonMesh.rotation.x = clampPitch(moonMesh.rotation.x + state.velocityX)

      state.prevX = event.clientX
      state.prevY = event.clientY
    }

    const handleWheel = (event: WheelEvent) => {
      if (exploringRef.current) {
        return
      }

      event.preventDefault()
      state.targetDistance = THREE.MathUtils.clamp(state.targetDistance + event.deltaY * 0.0032, 2.26, 5.35)
    }

    const resize = () => {
      const width = Math.max(container.clientWidth, 1)
      const height = Math.max(container.clientHeight, 1)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
    }

    renderer.domElement.addEventListener('pointerdown', handlePointerDown)
    renderer.domElement.addEventListener('pointermove', handlePointerMove)
    renderer.domElement.addEventListener('pointerup', releasePointer)
    renderer.domElement.addEventListener('pointercancel', releasePointer)
    renderer.domElement.addEventListener('pointerleave', handlePointerLeave)
    renderer.domElement.addEventListener('wheel', handleWheel, { passive: false })
    window.addEventListener('resize', resize)

    let animationFrameId = 0
    const clock = new THREE.Clock()

    const animate = () => {
      animationFrameId = window.requestAnimationFrame(animate)

      const elapsed = clock.getElapsedTime()

      if (!state.dragging && !exploringRef.current) {
        state.velocityX *= 0.95
        state.velocityY *= 0.95
        moonMesh.rotation.x = clampPitch(moonMesh.rotation.x + state.velocityX * 0.26)
        moonMesh.rotation.y += 0.0007 + state.velocityY * 0.34
      }

      if (exploringRef.current) {
        state.exploreProgress = Math.min(1, state.exploreProgress + 0.018)
        const eased = 1 - (1 - state.exploreProgress) ** 3
        state.targetDistance = THREE.MathUtils.lerp(BASE_CAMERA_DISTANCE, 1.46, eased)
        moonMesh.rotation.y += 0.011
        moonMesh.rotation.x = THREE.MathUtils.lerp(moonMesh.rotation.x, 0.1, 0.026)
        glowMaterial.opacity = 0.36 + state.exploreProgress * 0.14
      } else {
        state.exploreProgress = 0
        glowMaterial.opacity = 0.36
      }

      state.currentDistance = THREE.MathUtils.lerp(
        state.currentDistance,
        state.targetDistance,
        exploringRef.current ? 0.065 : 0.08,
      )
      camera.position.z = state.currentDistance

      moonGroup.rotation.z = Math.sin(elapsed * 0.18) * 0.016
      keyLight.position.x = 4.4 + Math.sin(elapsed * 0.18) * 0.12
      keyLight.position.y = 1.6 + Math.cos(elapsed * 0.14) * 0.06
      fillLight.position.x = -4.5 + Math.cos(elapsed * 0.16) * 0.08
      starField.rotation.y += 0.00006
      starFieldFar.rotation.y += 0.00002

      renderer.render(scene, camera)
    }

    animate()

    return () => {
      textureLoadCancelled = true
      window.cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', resize)
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown)
      renderer.domElement.removeEventListener('pointermove', handlePointerMove)
      renderer.domElement.removeEventListener('pointerup', releasePointer)
      renderer.domElement.removeEventListener('pointercancel', releasePointer)
      renderer.domElement.removeEventListener('pointerleave', handlePointerLeave)
      renderer.domElement.removeEventListener('wheel', handleWheel)
      releasePointer()

      moonGeometry.dispose()
      rimMesh.geometry.dispose()
      moonMaterial.dispose()
      rimMaterial.dispose()
      glowMaterial.dispose()
      disposePoints(starField)
      disposePoints(starFieldFar)
      renderer.dispose()

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
    }
  }, [onExplore])

  return (
    <section className={`landing-screen ${isExploring ? 'is-exiting' : ''}`}>
      <div ref={containerRef} className="landing-canvas" />

      <div className="landing-backdrop-grid" aria-hidden="true" />

      <div className="landing-brand">
        <span className="landing-brand-mark">LUNAPATH</span>
        <span className="landing-brand-sub">Lunar South Pole Route Planner</span>
      </div>

      <div className="landing-copy">
        <p className="landing-kicker">Mission Control Interface</p>
        <h1>Traverse the rim before the light window closes.</h1>
        <p className="landing-description">
          Inspect terrain risk, thermal exposure, and viable rover corridors from a single
          mission dashboard.
        </p>
      </div>

      <div className="landing-actions">
        <button
          type="button"
          className="landing-explore-button"
          onClick={() => setIsExploring(true)}
          disabled={isExploring}
        >
          [ Explore ]
        </button>
        <span className="landing-hint">Drag to rotate. Scroll to zoom.</span>
      </div>
    </section>
  )
}

function getGlowTexture(): THREE.CanvasTexture {
  if (cachedGlowTexture) {
    return cachedGlowTexture
  }

  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 256

  const ctx = canvas.getContext('2d')
  if (!ctx) {
    throw new Error('Unable to create glow texture.')
  }

  const gradient = ctx.createRadialGradient(128, 128, 18, 128, 128, 128)
  gradient.addColorStop(0, 'rgba(255,255,255,0.78)')
  gradient.addColorStop(0.34, 'rgba(170,184,255,0.34)')
  gradient.addColorStop(0.7, 'rgba(72,86,160,0.08)')
  gradient.addColorStop(1, 'rgba(0,0,0,0)')

  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  cachedGlowTexture = new THREE.CanvasTexture(canvas)
  cachedGlowTexture.colorSpace = THREE.SRGBColorSpace
  cachedGlowTexture.needsUpdate = true
  return cachedGlowTexture
}

function getMoonTexture(maxAnisotropy: number): Promise<THREE.CanvasTexture> {
  if (!cachedMoonTexturePromise) {
    cachedMoonTexturePromise = loadMoonTexture()
  }

  return cachedMoonTexturePromise.then((texture) => {
    texture.anisotropy = maxAnisotropy
    texture.needsUpdate = true
    return texture
  })
}

function loadMoonTexture(): Promise<THREE.CanvasTexture> {
  const loader = new THREE.ImageLoader()

  return new Promise((resolve, reject) => {
    loader.load(
      MOON_TEXTURE_PATH,
      (image) => resolve(createMoonCanvasTexture(image)),
      undefined,
      (error) => reject(error),
    )
  })
}

function createMoonCanvasTexture(image: HTMLImageElement | ImageBitmap): THREE.CanvasTexture {
  const width = 'naturalWidth' in image ? image.naturalWidth : image.width
  const height = 'naturalHeight' in image ? image.naturalHeight : image.height
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height

  const ctx = canvas.getContext('2d')
  if (!ctx) {
    throw new Error('Unable to create moon canvas texture.')
  }

  ctx.drawImage(image, 0, 0, width, height)
  const imageData = ctx.getImageData(0, 0, width, height)
  const { data } = imageData

  for (let index = 0; index < data.length; index += 4) {
    const value = data[index] / 255
    const shadowLifted = Math.pow(value, 0.8)
    const leveled = clamp01((shadowLifted - 0.04) / 0.93)
    const softenedContrast = clamp01((leveled - 0.5) * 0.96 + 0.54)
    const warmMix = clamp01(softenedContrast * 0.98 + 0.02)
    const red = clampByte(warmMix * 255)
    const green = clampByte((warmMix * 0.995 + 0.005) * 255)
    const blue = clampByte((softenedContrast * 1.03) * 255)

    data[index] = red
    data[index + 1] = green
    data[index + 2] = blue
  }

  ctx.putImageData(imageData, 0, 0)

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.ClampToEdgeWrapping
  texture.minFilter = THREE.LinearMipmapLinearFilter
  texture.magFilter = THREE.LinearFilter
  texture.needsUpdate = true
  return texture
}

function createStarField(
  count: number,
  innerRadius: number,
  outerRadius: number,
  pointSize: number,
  palette: number[],
) {
  const geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)

  for (let i = 0; i < count; i += 1) {
    const radius = innerRadius + Math.random() * (outerRadius - innerRadius)
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    const sinPhi = Math.sin(phi)
    const color = new THREE.Color(palette[Math.floor(Math.random() * palette.length)])

    positions[i * 3] = radius * sinPhi * Math.cos(theta)
    positions[i * 3 + 1] = radius * Math.cos(phi)
    positions[i * 3 + 2] = radius * sinPhi * Math.sin(theta)

    colors[i * 3] = color.r
    colors[i * 3 + 1] = color.g
    colors[i * 3 + 2] = color.b
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  return new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      size: pointSize,
      transparent: true,
      opacity: 0.82,
      sizeAttenuation: true,
      vertexColors: true,
      depthWrite: false,
    }),
  )
}

function disposePoints(points: THREE.Points) {
  points.geometry.dispose()

  const material = points.material
  if (Array.isArray(material)) {
    material.forEach((entry) => entry.dispose())
    return
  }

  material.dispose()
}

function clamp01(value: number) {
  return THREE.MathUtils.clamp(value, 0, 1)
}

function clampByte(value: number) {
  return Math.max(0, Math.min(255, Math.round(value)))
}
