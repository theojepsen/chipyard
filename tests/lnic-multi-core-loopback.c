#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include "lnic.h"

// #define MSG_LEN 8

bool is_single_core() { return false; }

void process_msgs() {
  uint64_t app_hdr;
  uint16_t msg_len;
  int num_words;
  int i;

  while (1) {
    // wait for a pkt to arrive
    lnic_wait();
    // read request application hdr
    app_hdr = lnic_read();
    // write response application hdr
    lnic_write_r(app_hdr);
    // extract msg_len
    msg_len = (uint16_t)app_hdr;
#ifdef MSG_LEN
    if (msg_len != MSG_LEN) {
      printf("ERROR: application only supports %d byte msgs!\n", MSG_LEN);
      return -1;
    }
    lnic_copy();
#else
    num_words = msg_len/LNIC_WORD_SIZE;
    if (msg_len % LNIC_WORD_SIZE != 0) { num_words++; }
    // copy msg words back into network
    for (i = 0; i < num_words; i++) {
      lnic_copy();
    }
#endif
    lnic_msg_done();
  }
}

int core_main() {
  uint64_t context_id = 0;
  uint64_t priority = 0;
  lnic_add_context(context_id, priority);

  process_msgs();

  return 0;
}

