// A PegBand bot in C++. Copy this folder to bots/<your-name>/ and write your strategy.
//
// The referee runs this program as a subprocess: one JSON message per line arrives on
// standard input, one JSON object per line goes back on standard output. Print anything you
// like to standard error for debugging. The referee ignores it.
//
// Squares are numbered 0 .. N*N-1, left to right and top to bottom: square i is in row i / N
// and column i % N.
//
// Messages you receive:
//   {"type":"start","color":"green","N":10,"pegs":5,"bands":5,"clock":120}
//       -> reply {"ready":true}.  This one is not on your clock.
//   {"type":"peg", ...}   -> reply {"peg":34}
//   {"type":"band", ...}  -> reply {"band":[12,34,56]}
//
// The messages also carry "board" (0 empty, 1 green peg, 2 blue peg), "your_pegs" and
// "their_pegs" as lists of square numbers. Only the few fields this template needs are
// parsed below; pull out more as your strategy needs them.

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

// -- the smallest amount of JSON reading this bot needs ----------------------

// The integer that follows "key": in the message, or fallback when it is not there.
static long long field(const std::string& line, const std::string& key, long long fallback = -1) {
    auto at = line.find("\"" + key + "\":");
    if (at == std::string::npos) return fallback;
    return std::strtoll(line.c_str() + at + key.size() + 3, nullptr, 10);
}

// The list of integers that follows "key": [ ... ].
// Use this for the flat lists: board, your_pegs, their_pegs, scores. The band lists
// (your_bands, their_bands) are lists of lists, so read those with list_of_lists.
static std::vector<int> list_field(const std::string& line, const std::string& key) {
    std::vector<int> out;
    auto at = line.find("\"" + key + "\":[");
    if (at == std::string::npos) return out;
    auto end = line.find(']', at);
    const char* p = line.c_str() + at + key.size() + 4;
    const char* stop = line.c_str() + end;
    while (p < stop) {
        char* next;
        long v = std::strtol(p, &next, 10);
        if (next == p) { ++p; continue; }
        out.push_back(static_cast<int>(v));
        p = next;
    }
    return out;
}

// The list of lists that follows "key": [[...],[...]], used for your_bands and their_bands.
static std::vector<std::vector<int>> list_of_lists(const std::string& line, const std::string& key) {
    std::vector<std::vector<int>> out;
    auto at = line.find("\"" + key + "\":[");
    if (at == std::string::npos) return out;
    int depth = 0;
    std::vector<int> cur;
    for (size_t i = at + key.size() + 3; i < line.size(); ++i) {
        char ch = line[i];
        if (ch == '[') {
            if (++depth == 2) cur.clear();
        } else if (ch == ']') {
            if (depth == 2) out.push_back(cur);
            if (--depth == 0) break;
        } else if (depth == 2 && (std::isdigit(static_cast<unsigned char>(ch)) || ch == '-')) {
            char* next;
            cur.push_back(static_cast<int>(std::strtol(line.c_str() + i, &next, 10)));
            i = static_cast<size_t>(next - line.c_str()) - 1;
        }
    }
    return out;
}

static bool has_type(const std::string& line, const char* what) {
    return line.find(std::string("\"type\":\"") + what + "\"") != std::string::npos;
}

// ----------------------------------------------------------------------------
// EDIT ONLY THIS SECTION
// ----------------------------------------------------------------------------

struct Bot {
    int N = 0, pegs = 0, bands = 0;

    void start(const std::string& line) {
        N = static_cast<int>(field(line, "N", 10));
        pegs = static_cast<int>(field(line, "pegs", 1));
        bands = static_cast<int>(field(line, "bands", 1));
    }

    // Return the square to put your next peg on.
    int place_peg(const std::string& line) {
        std::vector<int> mine = list_field(line, "your_pegs");
        std::vector<int> theirs = list_field(line, "their_pegs");
        std::vector<bool> taken(static_cast<size_t>(N) * N, false);
        for (int i : mine) taken[i] = true;
        for (int i : theirs) taken[i] = true;
        for (int i = 0; i < N * N; ++i) if (!taken[i]) return i;
        return 0;
    }

    // Return the pegs of yours to stretch this rubberband around. The band is their convex
    // hull, so the order does not matter. It must not contain or touch an enemy peg.
    std::vector<int> place_band(const std::string& line) {
        std::vector<int> mine = list_field(line, "your_pegs");
        if (mine.size() > 1) mine.resize(1);
        return mine;
    }
};

// ----------------------------------------------------------------------------
// Below here is the plumbing. You should not need to change it.
// ----------------------------------------------------------------------------

int main() {
    std::ios::sync_with_stdio(false);
    Bot bot;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        if (has_type(line, "start")) {
            bot.start(line);
            std::cout << "{\"ready\":true}\n" << std::flush;
        } else if (has_type(line, "peg")) {
            std::cout << "{\"peg\":" << bot.place_peg(line) << "}\n" << std::flush;
        } else if (has_type(line, "band")) {
            std::vector<int> band = bot.place_band(line);
            std::cout << "{\"band\":[";
            for (size_t i = 0; i < band.size(); ++i) {
                if (i) std::cout << ',';
                std::cout << band[i];
            }
            std::cout << "]}\n" << std::flush;
        } else {
            std::cout << "{}\n" << std::flush;
        }
    }
    return 0;
}
