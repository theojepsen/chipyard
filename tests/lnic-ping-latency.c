#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include "lnic.h"

#define CLIENT_IP 0x0a000001
#define CLIENT_CONTEXT 0

#define SERVER_IP 0x0a000001
#define SERVER_CONTEXT 1

#define NUM_MSGS 10
#define MSG_LEN_WORDS 1

bool is_single_core() { return false; }

int run_client() {
  uint64_t app_hdr;
  uint64_t dst_ip;
  uint64_t dst_context;
  uint64_t now;
  uint64_t latency;
  int i;
  int n;

  dst_ip = SERVER_IP;
  dst_context = SERVER_CONTEXT;

  for (n = 0; n < NUM_MSGS; n++) {
    // Send msg to server
    app_hdr = (dst_ip << 32) | (dst_context << 16) | (MSG_LEN_WORDS*8);
    //printf("Sending message\n");
    lnic_write_r(app_hdr);
    lnic_write_r(rdcycle());

    // receive response from server
    lnic_wait();
    app_hdr = lnic_read();
    // Record latency
    now = rdcycle();
    latency = now - lnic_read();
    printf("time = %lld cycles, latency = %lld cycles\n", now, latency);
    // Check src IP
    uint64_t src_ip = (app_hdr & IP_MASK) >> 32;
    if (src_ip != SERVER_IP) {
        printf("ERROR: Expected: correct_sender_ip = %lx, Received: src_ip = %lx\n", SERVER_IP, src_ip);
        return -1;
    }
    // Check src context
    uint64_t src_context = (app_hdr & CONTEXT_MASK) >> 16;
    if (src_context != SERVER_CONTEXT) {
        printf("ERROR: Expected: correct_src_context = %ld, Received: src_context = %ld\n", SERVER_CONTEXT, src_context);
        return -1;
    }
    // Check msg length
    uint16_t rx_msg_len = app_hdr & LEN_MASK;
    if (rx_msg_len != MSG_LEN_WORDS*8) {
        printf("ERROR: Expected: msg_len = %d, Received: msg_len = %d\n", MSG_LEN_WORDS*8, rx_msg_len);
        return -1;
    }
    lnic_msg_done();
  }

  // make sure RX queue is empty
  if (read_csr(0x052) != 0) {
    printf("ERROR: RX Queue is not empty after processing all msgs!\n");
    return -1;
  }

  return 0; 
}
 
int run_server() {
  uint64_t app_hdr;
  uint16_t msg_len;
  int num_words;
  int i;
  int n;

  for (n = 0; n < NUM_MSGS; n++) {
    // wait for a pkt to arrive
    lnic_wait();
    // read request application hdr
    app_hdr = lnic_read();
    // write response application hdr
    lnic_write_r(app_hdr);
    // extract msg_len
    msg_len = (uint16_t)app_hdr;
//    printf("Received msg of length: %hu bytes", msg_len);
    num_words = msg_len/LNIC_WORD_SIZE;
    if (msg_len % LNIC_WORD_SIZE != 0) { num_words++; }
    // copy msg words back into network
    for (i = 0; i < num_words; i++) {
      lnic_copy();
    }
    lnic_msg_done();
  }

  // make sure RX queue is empty
  if (read_csr(0x052) != 0) {
    printf("ERROR: RX Queue is not empty after processing all msgs!\n");
    return -1;
  }

  return 0;
}

int core_main(uint64_t argc, char** argv, int cid, int nc) {
  uint64_t context_id = cid;
  uint64_t priority = 0;
  lnic_add_context(context_id, priority);

  // wait for all cores to boot -- TODO: is there a better way than this?
  for (int i = 0; i < 1000; i++) {
    asm volatile("nop");
  }

  int ret = 0;
  if (cid == 0) {
    ret = run_client();
  } else if (cid == 1) {
    ret = run_server();
  }
 
  return ret;
}

