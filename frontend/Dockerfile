# ==========================================
# Stage 1: Build Next.js app
# ==========================================
FROM node:18-alpine AS builder

WORKDIR /app

# Copy dependency configuration
COPY package*.json ./

# Install npm dependencies
RUN npm ci

# Copy application code
COPY . .

# Disable telemetry and build
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ==========================================
# Stage 2: Runtime Container
# ==========================================
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0

# Copy necessary assets and build files
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

# Start Next.js server
CMD ["npm", "run", "start"]
