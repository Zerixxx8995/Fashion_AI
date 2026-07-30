/**
 * Socket Manager — api-backend integrations layer.
 *
 * Responsibility: Own the Socket.io server lifecycle and expose a clean API
 * for emitting targeted events to connected users.
 *
 * Architecture rules:
 *   Layer: Integrations
 *   One job: Socket.io setup and user-targeted event dispatch
 *   Never does: Business logic, HTTP routing, DB access
 *
 * Usage:
 *   const { initSocket, emitToUser } = require('./socketManager');
 *   const io = initSocket(httpServer);
 *   emitToUser(userId, 'price_drop', { alertId, newPrice });
 *
 * Client connection:
 *   Socket clients must send their internal user UUID via query param or auth:
 *     socket.handshake.auth.userId  (preferred)
 *   The server joins the socket to a private room keyed by userId.
 */

'use strict';

const { Server } = require('socket.io');

let _io = null;

/**
 * Initialise Socket.io on an existing http.Server.
 * Must be called once at server startup.
 *
 * @param {import('http').Server} httpServer
 * @returns {import('socket.io').Server}
 */
function initSocket(httpServer) {
  _io = new Server(httpServer, {
    cors: {
      origin: process.env.ALLOWED_ORIGINS ? process.env.ALLOWED_ORIGINS.split(',') : '*',
      methods: ['GET', 'POST'],
    },
    // Disable long-polling — WS only for this service
    transports: ['websocket'],
  });

  _io.on('connection', (socket) => {
    const userId = socket.handshake.auth?.userId;
    if (userId) {
      // Each user gets a private room — rooms are free and auto-cleaned
      socket.join(`user:${userId}`);
      console.log(`[socket_manager] client connected userId=${userId} socketId=${socket.id}`);
    } else {
      console.warn(`[socket_manager] client connected without userId — cannot target events. socketId=${socket.id}`);
    }

    socket.on('disconnect', () => {
      console.log(`[socket_manager] client disconnected socketId=${socket.id}`);
    });
  });

  console.log('[socket_manager] Socket.io initialised');
  return _io;
}

/**
 * Get the Socket.io server instance.
 * Throws if initSocket has not been called yet.
 *
 * @returns {import('socket.io').Server}
 */
function getIO() {
  if (!_io) {
    throw new Error('[socket_manager] Socket.io not initialised. Call initSocket(httpServer) first.');
  }
  return _io;
}

/**
 * Emit a named event to a specific user's private room.
 *
 * @param {string} userId     - Internal UUID of the target user
 * @param {string} eventName  - Socket event name (e.g. 'price_drop', 'restock')
 * @param {object} payload    - JSON-serialisable event payload
 */
function emitToUser(userId, eventName, payload) {
  if (!_io) {
    // In test environments Socket.io may not be running — log but don't throw
    console.warn(`[socket_manager] emitToUser called but Socket.io not initialised. userId=${userId} event=${eventName}`);
    return;
  }
  _io.to(`user:${userId}`).emit(eventName, payload);
  console.log(`[socket_manager] emitted event=${eventName} to userId=${userId}`);
}

module.exports = { initSocket, getIO, emitToUser };
